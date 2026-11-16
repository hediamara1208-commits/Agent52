import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-serif/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./styles/theme.css";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ReplayApp, isReplay } from "./replay/ReplayApp";
import { createAmplifyAuth } from "./api/auth";
import { createApiClient, loadConfig } from "./api/client";
import { guestToken } from "./api/guest";

const root = createRoot(document.getElementById("root")!);
if (isReplay(window.location.search, import.meta.env.MODE)) {
  // Replay_Mode: no config fetch, no sign-in, no Session_API (Req. 35.3).
  root.render(<ReplayApp />);
} else {
  loadConfig()
    .then((config) => {
      if (config.guest) {
        root.render(<App makeApi={() => createApiClient(config, guestToken)} />);
        return;
      }
      const auth = createAmplifyAuth(config);
      root.render(<App auth={auth} makeApi={() => createApiClient(config, () => auth.apiToken())} />);
    })
    .catch((e) => root.render(<p role="alert">{e instanceof Error ? e.message : "Configuration error"}</p>));
}
