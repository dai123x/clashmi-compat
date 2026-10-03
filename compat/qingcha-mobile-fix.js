// Clash Mi 清茶云/CN 网络延迟修复覆写(官方版 Clash Mi 可直接使用)
//
// 用法: Clash Mi → 订阅/配置 → 覆写(补丁) → 新建 → 脚本 → 粘贴本文件全部内容,
//       然后把该覆写挂到清茶云订阅上,重新连接生效。
//
// 修复内容(均已在本仓库 compat_test 中用真实清茶云订阅 + mihomo v1.19.25/v1.19.31 实测):
//   1. DNS 全部换为国内直连可达的解析服务。
//      机场节点域名(如 az*.qczh***.work)在混合境外 DNS 下会被污染/解析失败,
//      内核日志表现为 "dns resolve failed: couldn't find ip",
//      UI 表现为大部分节点 "http response timeout after 5 seconds"。
//   2. 移除订阅自带的境外 DNS fallback(国内直连全部不可达,只会拖死解析)。
//   3. 开启 tcp-concurrent:节点域名解析出多个 IP 时并发竞速连接,
//      手机 IPv4/IPv6 双栈网络下提速明显。
//   4. 开启 unified-delay:测速结果扣除握手耗时,与 PC 端 Clash Verge 口径一致。
//   5. 清除 global-client-fingerprint:清茶云节点自带 client-fingerprint: safari,
//      全局覆盖已被新版 mihomo 移除(报 error 日志),旧内核上还会压制节点自带指纹。
function main(config) {
  if (!config) {
    return config;
  }

  // 1/3/4: 连接与测速优化
  config["unified-delay"] = true;
  config["tcp-concurrent"] = true;

  // 5: 不让任何全局指纹覆盖节点自带的 safari
  delete config["global-client-fingerprint"];

  // 2 + 5: DNS 重置为纯国内可达解析
  var dns = config.dns || {};
  dns.enable = true;
  dns.ipv6 = dns.ipv6 === true ? true : false;
  if (!dns["enhanced-mode"]) {
    dns["enhanced-mode"] = "fake-ip";
  }
  if (!dns["fake-ip-range"]) {
    dns["fake-ip-range"] = "198.18.0.1/16";
  }
  dns.nameserver = [
    "223.5.5.5",
    "119.29.29.29",
    "tls://223.5.5.5:853",
    "https://dns.alidns.com/dns-query#h3=true",
  ];
  dns["default-nameserver"] = ["223.5.5.5", "119.29.29.29"];
  // 关键:节点服务器域名必须只用国内 DNS 解析,否则被污染即 5 秒超时
  dns["proxy-server-nameserver"] = [
    "223.5.5.5",
    "119.29.29.29",
    "tls://223.5.5.5:853",
  ];
  dns["direct-nameserver"] = ["223.5.5.5", "119.29.29.29", "system"];
  delete dns.fallback;
  delete dns["fallback-filter"];
  config.dns = dns;

  return config;
}
