# Clash Mi 清茶云延迟修复包

手机上 Clash Mi 用清茶云订阅,节点测速大面积 `http response timeout after 5 seconds`、
剩下几个也是 1500~3000ms;同一订阅在电脑 Clash Verge 上却一切正常?

这不是内核不兼容,也不是订阅坏了——是 **DNS 配置问题**,本包一行不改内核即可修复。

## 根因(30 秒版)

1. 清茶云订阅自带境外 DNS fallback(`doh.dns.sb` / `dns.cloudflare.com` / `tls://8.8.4.4`),
   国内网络直连全部不可达;
2. Clash Mi 默认注入的 DNS 列表又混入了大量境外明文 DNS(`8.8.8.8` / `1.1.1.1` / adguard 等),
   手机运营商网络下这些解析会被污染或丢包;
3. 机场节点服务器域名(`az*.qczh***.work`)因此解析失败或拿到假 IP,
   内核日志:`connect error: dns resolve failed: couldn't find ip`;
   UI 表现:大部分节点 `http response timeout after 5 seconds`。
4. 电脑端 Clash Verge 正常,只是因为它的 DNS 覆写恰好是纯国内解析。

实测(mihomo v1.19.31,即 Clash Mi 当前内核,同一台电脑同一订阅):

| DNS 配置 | 节点连通性 |
| --- | --- |
| 订阅原始 DNS(境外 fallback) | `dns resolve failed: couldn't find ip`,完全不通 |
| Clash Mi 现行默认(混合境外) | 通但每次请求 1.0~1.9s(慢 3~4 倍),手机网络上恶化为超时 |
| **纯国内 DNS(本修复)** | **通,内核内测速 420ms(日本02)** |

## 用法(官方版 Clash Mi,无需刷机/重装)

1. 打开 Clash Mi → 底部「配置」→ 找到「覆写 / 补丁」入口;
2. 新建覆写,类型选 **脚本**,把本目录 [`qingcha-mobile-fix.js`](qingcha-mobile-fix.js) 的全部内容粘贴进去;
3. 把该覆写挂到清茶云订阅上;
4. 断开重连一次,进「代理」页重新测速。

## 脚本做了什么

- `dns.nameserver` / `default-nameserver` / `proxy-server-nameserver` / `direct-nameserver`
  → 全部换成国内直连可达(223.5.5.5 / 119.29.29.29 / DoT / AliDNS DoH);
- 删除 `dns.fallback` / `fallback-filter`(订阅自带的境外 fallback 是拖死解析的元凶);
- `tcp-concurrent: true`(多 IP 并发竞速连接,手机双栈网络提速明显);
- `unified-delay: true`(测速扣除握手耗时,与 PC 端 Clash Verge 口径一致);
- 删除 `global-client-fingerprint`(新版 mihomo 已移除该配置,且不应覆盖节点自带的
  `client-fingerprint: safari`)。

## 常见问题

**改完还是有节点超时?**
先在手机浏览器里直接打开 `https://www.gstatic.com/generate_204` 确认基础网络;
再切换一个节点测速。若个别节点仍超时而多数正常,那是机场节点本身的线路问题,与本修复无关。

**电脑上需要吗?**
电脑 Clash Verge 已在上一轮排查中通过 `dns_config.yaml` 覆写修复,无需重复处理。

**为什么 Clash Mi 不直接修?**
Clash Mi 官方默认 DNS 面向全球用户混合了大量境外解析,在纯国内网络(尤其手机运营商)下
才有此问题。本仓库 fork 已把默认值改为纯国内解析(`lib/app/modules/clash_setting_manager.dart`),
但 Clash Mi 的 VPN 服务插件闭源,无法从公开源码出安装包,所以提供本脚本让官方版直接使用。
