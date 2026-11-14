export {};

declare global {
  interface Window {
    devharborDesktop?: {
      getRuntime: () => Promise<{ apiBaseUrl: string; token: string; dataDirectory: string }>;
      restart: () => Promise<void>;
    };
  }
}
