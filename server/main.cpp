// EngLab transitional C++ static server.
// It deliberately serves an explicit public artifact set and is not the FastAPI backend.

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif

#include <httplib.h>

#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace fs = std::filesystem;

std::string path_to_utf8(const fs::path& path) {
#ifdef _WIN32
    const auto wide = path.wstring();
    if (wide.empty()) {
        return {};
    }
    const int wide_size = static_cast<int>(wide.size());
    const int size = WideCharToMultiByte(CP_UTF8, 0, wide.data(), wide_size, nullptr, 0, nullptr, nullptr);
    if (size <= 0) {
        throw std::runtime_error("Unable to encode public asset path as UTF-8");
    }
    std::string value(static_cast<std::size_t>(size), '\0');
    if (WideCharToMultiByte(CP_UTF8, 0, wide.data(), wide_size, value.data(), size, nullptr, nullptr) != size) {
        throw std::runtime_error("Unable to encode public asset path as UTF-8");
    }
    return value;
#else
    return path.string();
#endif
}

std::string get_mime_type(const std::string& path) {
    static const std::unordered_map<std::string, std::string> mime_map = {
        {".html", "text/html; charset=utf-8"},
        {".css", "text/css; charset=utf-8"},
        {".js", "application/javascript; charset=utf-8"},
        {".json", "application/json; charset=utf-8"},
        {".png", "image/png"},
        {".jpg", "image/jpeg"},
        {".jpeg", "image/jpeg"},
        {".gif", "image/gif"},
        {".svg", "image/svg+xml"},
        {".ico", "image/x-icon"},
        {".webp", "image/webp"},
        {".woff", "font/woff"},
        {".woff2", "font/woff2"},
        {".ttf", "font/ttf"},
        {".mp4", "video/mp4"},
        {".webm", "video/webm"},
    };
    const auto extension = fs::path(path).extension().string();
    const auto found = mime_map.find(extension);
    return found != mime_map.end() ? found->second : "application/octet-stream";
}

std::string now_iso() {
    const auto now = std::chrono::system_clock::now();
    const auto value = std::chrono::system_clock::to_time_t(now);
    std::tm local{};
#ifdef _WIN32
    localtime_s(&local, &value);
#else
    localtime_r(&value, &local);
#endif
    char buffer[64];
    std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%S", &local);
    return buffer;
}

void log_request(const httplib::Request& request, const httplib::Response& response) {
    std::cout << "[" << now_iso() << "] " << request.method << " " << request.path << " -> "
              << response.status << " (" << response.body.size() << " bytes)" << std::endl;
}

int main(int argc, char* argv[]) {
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
#endif

    int port = 9527;
    std::string host = "127.0.0.1";
    std::string root_directory = "..";
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if ((argument == "-p" || argument == "--port") && index + 1 < argc) {
            port = std::stoi(argv[++index]);
        } else if (argument == "--host" && index + 1 < argc) {
            host = argv[++index];
        } else if ((argument == "-r" || argument == "--root") && index + 1 < argc) {
            root_directory = argv[++index];
        } else if (argument == "-h" || argument == "--help") {
            std::cout << "Usage: englab_server [OPTIONS]\n"
                      << "  -p, --port PORT   Server port (default: 9527)\n"
                      << "      --host HOST   Bind host (default: 127.0.0.1)\n"
                      << "  -r, --root DIR    Project root containing the public artifacts (default: ..)\n"
                      << "  -h, --help        Show this help\n";
            return 0;
        }
    }

    const auto absolute_root = fs::absolute(fs::path(root_directory)).lexically_normal();
    if (!fs::is_regular_file(absolute_root / "index.html")) {
        std::cerr << "ERROR: index.html not found in the configured project root\n";
        return 1;
    }

    httplib::Server server;
    server.set_default_headers({{"X-Content-Type-Options", "nosniff"}});

    server.Get("/api/health", [](const httplib::Request&, httplib::Response& response) {
        response.set_content(R"({"status":"ok","server":"englab-cpp"})", "application/json");
    });
    server.Get("/api/info", [](const httplib::Request&, httplib::Response& response) {
        std::ostringstream body;
        body << R"({"server":"EngLab C++ Server","version":"1.1.0",)"
             << R"("time":")" << now_iso() << R"("})";
        response.set_content(body.str(), "application/json");
    });
    server.Post("/api/eval", [](const httplib::Request&, httplib::Response& response) {
        response.set_content(
            R"({"result":null,"message":"Math eval endpoint - to be implemented with safe parser"})",
            "application/json"
        );
    });

    // Do not mount the repository root. Only these reviewed browser artifacts are public.
    for (const auto* directory : {"pages", "shared", "UI", "codevis"}) {
        const auto public_directory = absolute_root / directory;
        if (fs::is_directory(public_directory)) {
            server.set_mount_point("/" + std::string(directory), path_to_utf8(public_directory));
        }
    }
    const auto serve_root_file = [&absolute_root](const std::string& name, httplib::Response& response) {
        const auto file_path = absolute_root / name;
        std::ifstream file(file_path, std::ios::binary);
        if (!file) {
            response.status = 404;
            return;
        }
        std::ostringstream body;
        body << file.rdbuf();
        response.set_content(body.str(), get_mime_type(file_path.string()));
    };
    server.Get("/", [&serve_root_file](const httplib::Request&, httplib::Response& response) {
        serve_root_file("index.html", response);
    });
    server.Get("/index.html", [&serve_root_file](const httplib::Request&, httplib::Response& response) {
        serve_root_file("index.html", response);
    });
    server.Get("/sw.js", [&serve_root_file](const httplib::Request&, httplib::Response& response) {
        serve_root_file("sw.js", response);
    });

    server.set_logger([](const httplib::Request& request, const httplib::Response& response) {
        log_request(request, response);
    });
    server.set_error_handler([](const httplib::Request&, httplib::Response& response) {
        response.set_content(
            R"({"error":")" + std::to_string(response.status) + R"(","message":"Not Found"})",
            "application/json"
        );
    });

    std::cout << "EngLab C++ static server\n"
              << "  Public artifact allowlist: index.html, sw.js, pages/, shared/, UI/, codevis/\n"
              << "  URL: http://" << host << ":" << port << "\n";
    if (!server.listen(host, port)) {
        std::cerr << "ERROR: Failed to start server on " << host << ":" << port << "\n";
        return 1;
    }
    return 0;
}
