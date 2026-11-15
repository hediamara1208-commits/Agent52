import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ReplayApp, isReplay } from "./replay/ReplayApp";
import { createAmplifyAuth } from "./api/auth";
import { createApiClient, loadConfig } from "./api/client";

const root = createRoot(document.getElementById("root")!);
if (isReplay(window.location.search, import.meta.env.MODE)) {
  // Replay_Mode: no config fetch, no sign-in, no Session_API (Req. 35.3).
  root.render(<ReplayApp />);
} else {
  loadConfig()
    .then((config) => {
      const auth = createAmplifyAuth(config);
      root.render(<App auth={auth} makeApi={() => createApiClient(config, () => auth.accessToken())} />);
    })
    .catch((e) => root.render(<p role="alert">{e instanceof Error ? e.message : "Configuration error"}</p>));
}
