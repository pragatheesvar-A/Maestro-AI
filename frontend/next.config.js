/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Avoids a known flaky ENOENT race in Next 14's build-trace collection
  // step on Windows (antivirus/file-locking related) that isn't needed for
  // this app anyway (we deploy via `next start` / Docker, not serverless
  // functions that rely on file tracing).
  outputFileTracing: false,
};

module.exports = nextConfig;
