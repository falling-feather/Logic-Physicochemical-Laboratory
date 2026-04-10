// ===== 工科实验室 · C++ Backend Server =====
// Lightweight HTTP server for static files + REST API
// Built with cpp-httplib (header-only)

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif

#include <httplib.h>
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <chrono>
#include <ctime>
#include <filesystem>

namespace fs = std::filesystem;

// ─── MIME type mapping ───
std::string get_mime_type(const std::string& path) {
    static const std::unordered_map<std::string, std::string> mime_map = {
        {".html", "text/html; charset=utf-8"},
        {".css",  "text/css; charset=utf-8"},
        {".js",   "application/javascript; charset=utf-8"},
        {".json", "application/json; charset=utf-8"},
        {".png",  "image/png"},
        {".jpg",  "image/jpeg"},
        {".jpeg", "image/jpeg"},
        {".gif",  "image/gif"},
        {".svg",  "image/svg+xml"},
        {".ico",  "image/x-icon"},
        {".webp", "image/webp"},
        {".woff", "font/woff"},
        {".woff2","font/woff2"},
        {".ttf",  "font/ttf"},
        {".mp4",  "video/mp4"},
        {".webm", "video/webm"},
    };
    auto ext = fs::path(path).extension().string();
    auto it = mime_map.find(ext);
    return (it != mime_map.end()) ? it->second : "application/octet-stream";
}

// ─── Timestamp helper ───
std::string now_iso() {
    auto now = std::chrono::system_clock::now();
    auto t = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
#ifdef _WIN32
    localtime_s(&tm, &t);
#else
    localtime_r(&t, &tm);
#endif
    char buf[64];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", &tm);
    return buf;
}

// ─── Request logging ───
void log_request(const httplib::Request& req, const httplib::Response& res) {
    std::cout << "[" << now_iso() << "] "
              << req.method << " " << req.path
              << " → " << res.status
              << " (" << res.body.size() << " bytes)"
              << std::endl;
}

int main(int argc, char* argv[]) {
#ifdef _WIN32
    // Enable UTF-8 console output and filesystem paths
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
#endif

    int port = 9527;
    std::string root_dir = "..";   // default: parent directory = project root

    // Parse args
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if ((arg == "-p" || arg == "--port") && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if ((arg == "-r" || arg == "--root") && i + 1 < argc) {
            root_dir = argv[++i];
        } else if (arg == "-h" || arg == "--help") {
            std::cout << "Usage: englab_server [OPTIONS]\n"
                      << "  -p, --port PORT   Server port (default: 9527)\n"
                      << "  -r, --root DIR    Web root directory (default: ..)\n"
                      << "  -h, --help        Show this help\n";
            return 0;
        }
    }

    // Resolve root directory
    auto abs_root = fs::absolute(fs::path(root_dir)).lexically_normal();
    if (!fs::exists(abs_root / "index.html")) {
        std::cerr << "ERROR: index.html not found in root dir\n"
                  << "  Use --root to specify the web root directory.\n";
        return 1;
    }

    // Convert to narrow string for httplib (use Windows API for proper conversion)
    std::string root_str;
#ifdef _WIN32
    {
        auto wpath = abs_root.wstring();
        int sz = WideCharToMultiByte(CP_UTF8, 0, wpath.c_str(), -1, nullptr, 0, nullptr, nullptr);
        root_str.resize(sz - 1);
        WideCharToMultiByte(CP_UTF8, 0, wpath.c_str(), -1, &root_str[0], sz, nullptr, nullptr);
    }
#else
    root_str = abs_root.string();
#endif

    httplib::Server svr;

    // ─── CORS headers ───
    svr.set_default_headers({
        {"Access-Control-Allow-Origin", "*"},
        {"Access-Control-Allow-Methods", "GET, POST, OPTIONS"},
        {"Access-Control-Allow-Headers", "Content-Type"}
    });

    // ─── API: Health check ───
    svr.Get("/api/health", [](const httplib::Request&, httplib::Response& res) {
        res.set_content(R"({"status":"ok","server":"englab-cpp"})", "application/json");
    });

    // ─── API: Server info ───
    svr.Get("/api/info", [&root_str](const httplib::Request&, httplib::Response& res) {
        std::ostringstream oss;
        oss << R"({"server":"EngLab C++ Server","version":"1.0.0",)"
            << R"("root":")" << root_str << R"(",)"
            << R"("time":")" << now_iso() << R"("})";
        res.set_content(oss.str(), "application/json");
    });

    // ─── API: Evaluate math expression (basic) ───
    svr.Post("/api/eval", [](const httplib::Request& req, httplib::Response& res) {
        // Simple math evaluation endpoint - to be extended
        // For security, only allow basic arithmetic
        auto body = req.body;
        res.set_content(R"({"result":null,"message":"Math eval endpoint - to be implemented with safe parser"})",
                       "application/json");
    });

    // ─── Static file serving ───
    svr.set_mount_point("/", root_str);

    // ─── Post-routing logging ───
    svr.set_logger([](const httplib::Request& req, const httplib::Response& res) {
        log_request(req, res);
    });

    // ─── Error handler ───
    svr.set_error_handler([](const httplib::Request&, httplib::Response& res) {
        res.set_content(
            R"({"error":")" + std::to_string(res.status) + R"(","message":"Not Found"})",
            "application/json"
        );
    });

    std::cout << "╔══════════════════════════════════════════╗\n"
              << "║   EngLab C++ Server                      ║\n"
              << "╠══════════════════════════════════════════╣\n"
              << "║  Port:  " << port << std::string(33 - std::to_string(port).size(), ' ') << "║\n"
              << "╚══════════════════════════════════════════╝\n"
              << "\n  Root: " << root_str
              << "\n  URL:  http://localhost:" << port << "\n\n";

    if (!svr.listen("0.0.0.0", port)) {
        std::cerr << "ERROR: Failed to start server on port " << port << "\n";
        return 1;
    }

    return 0;
}
