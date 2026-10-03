# 兼容版技术档案:清茶云订阅 × Clash Mi

本文档记录 2026-10-03 对「电脑 Clash Verge 正常、手机 Clash Mi 用清茶云大面积超时」的完整排查,
以及本 fork 的修改依据。所有结论均有本机可复现实验支撑。

## 1. 环境与对象

- 订阅:清茶云(Clash YAML 格式,26 个节点,全部为 `vless + reality(xtls-rprx-vision)`,
  节点自带 `client-fingerprint: safari`,`reality-opts.short-id: null`)
- 手机端:Clash Mi 官方 v1.0.30.x(内嵌 mihomo **v1.19.31**,`clashmiService.exe`/内核服务来自
  KaringX 私有仓库 `libclash-builder`)
- 电脑端:clash-verge-rev 兼容分支(内嵌 mihomo **v1.19.25**,即 `verge-mihomo-compat`)
- 症状:手机「代理」页大部分节点 `http response timeout after 5 seconds`,
  少数 1500~3000ms;电脑端同订阅节点延迟正常。

## 2. 排除项(都实测过,不是原因)

| 假设 | 实验结论 |
| --- | --- |
| 新内核解析不了清茶云订阅 | ❌ 原始订阅在 v1.19.25 与 v1.19.31 上 `mihomo -t` 全部通过 |
| mihomo v1.19.26~31 存在 REALITY 解析回归 | ❌ 双版本守护进程并行实测,行为一致(见 §3) |
| `global-client-fingerprint: chrome`(Clash Mi 默认注入)覆盖节点 safari 指纹 | ❌ v1.19.31 已移除该配置(仅打 error 日志并忽略);但注入本身是死代码,本 fork 仍移除 |
| 订阅 YAML 写法(如 `short-id: null`) | ❌ 两版内核均按空串处理,解析无差异 |

## 3. 决定性实验:同一台电脑、同一订阅、双内核并行

在 PC 上同时运行 v1.19.25 与 v1.19.31 两个实例(混合端口 17890/17891),
通过外部控制器选中同一节点后用 `curl -x` 实测:

### 3.1 使用订阅原始 DNS(境外 fallback:doh.dns.sb / cloudflare / twnic / tls 8.8.4.4)

```
两个内核日志同时出现:
dial 清茶云 ... error: az1.qczh***.work:24801 connect error:
dns resolve failed: couldn't find ip
curl 经两个内核端口: http_code=000, 5s 超时
```

**双内核行为完全一致 → 内核无回归,故障在 DNS 解析层。**

### 3.2 换成纯国内 DNS(nameserver/default/proxy-server-nameserver 全部 CN 可达)

```
v1.19.25: http_code=204, time=1.36s / 1.22s(冷启动)
v1.19.31: http_code=204, time=0.55s / 0.44s
节点内测速(日本 02): {"delay": 420}   <- 手机截图上该节点是 5 秒超时
```

### 3.3 Clash Mi 现行默认 DNS(混合 8.8.8.8 / 1.1.1.1 / cloudflare / adguard 等)

```
v1.19.25: http_code=204, time=1.46s / 1.90s / 1.90s
v1.19.31: http_code=204, time=1.52s / 1.55s / 1.05s
```

PC 宽带下混合列表只是慢 3~4 倍(每次解析都要陪境外服务器跑完竞速),
手机运营商网络下境外 UDP 被污染/丢包更彻底,即表现为大面积 5 秒超时。

## 4. 与 2026-05 verge 事件的关系

上次 clash-verge-rev v2.5.2+ 的「节点 Unknown/解析失败」当时未定位到字段,只归结为
"Inline Provider 相关",并以内置 mihomo v1.19.25 兼容内核规避。本次实验表明:
**清茶云原始订阅对新内核完全兼容,当时的故障同样源于 DNS/配置合成链路,而非内核解析。**
verge 侧的修复(dns_config.yaml 写非空 CN fallback)与本仓库的修复同源。

## 5. 修复方案

同一组修改以两种形态交付:

1. **官方版立即可用**:`compat/qingcha-mobile-fix.js` 覆写脚本(手机粘贴即用,见 compat/README.md);
2. **fork 源码默认值**(`lib/app/modules/clash_setting_manager.dart`):
   - `defaultDNS()`:四组解析列表全部改为国内可达,`fallback` 置空;
   - `defaultConfig()`:`UnifiedDelay: true`、`TCPConcurrent: true`、不再注入全局指纹;
   - `getPatchContent()`:迁移逻辑——老用户存量设置里的全局指纹在生成补丁时清除。

## 6. 已知限制

- Clash Mi 的 VPN 服务插件(`libclash_vpn_service`)与机场面板插件(`board_service`)为
  KaringX 私有仓库(上游 issue [#372](https://github.com/KaringX/clashmi/issues/372)、
  [#466](https://github.com/KaringX/clashmi/issues/466)),**公开源码无法构建出完整安装包**,
  因此本仓库不发布安装包,以源码补丁 + 官方版覆写脚本交付。
- `compat_test/` 中的订阅样本已脱敏(uuid/服务器/公钥均为占位符),字段形态与真实订阅一致,
  用于 CI 持续盯住 mihomo 新版本的解析兼容性(防止再次出现 verge 式回归)。
