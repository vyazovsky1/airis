<?php
// Runs ONCE at PHP-FPM/Apache startup — not per request

$log = function(string $msg) {
    $ts = date('Y-m-d H:i:s');
    error_log("[PRELOAD $ts] $msg");
};

$log("Server startup triggered");

// --- 1GB allocation stress at startup ---
ini_set('memory_limit', '1200M');

$target = 1 * 1024 * 1024 * 1024;
$before = memory_get_usage(true);
$t0     = microtime(true);

$block  = str_repeat("\x00", $target);

$elapsed = round((microtime(true) - $t0) * 1000, 2);
$delta   = round((memory_get_usage(true) - $before) / 1048576, 1);

$log("1GB block allocated | delta={$delta}MB | time={$elapsed}ms");

// Read OS-level RSS for real physical memory confirmation
$status = @file_get_contents('/proc/self/status');
if ($status && preg_match('/VmRSS:\s+(\d+)\s+kB/', $status, $m)) {
    $log("VmRSS (OS): " . round($m[1] / 1024, 1) . " MB");
}

unset($block);
$log("Block released. Startup complete.");

// Optionally preload your main app file into OPcache
opcache_compile_file(__DIR__ . '/guestbook.php');
$log("guestbook.php preloaded into OPcache");
?>
