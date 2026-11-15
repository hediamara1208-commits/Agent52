// Amplify Auth wrapper against the Cognito user pool named in config.json.
import { Amplify } from "aws-amplify";
import { fetchAuthSession, getCurrentUser, signIn, signOut } from "aws-amplify/auth";
import type { RuntimeConfig } from "./client";

export interface AuthService {
  currentUser(): Promise<string | null>;
  signIn(username: string, password: string): Promise<void>;
  signOut(): Promise<void>;
  /** Cognito ID token for the Session_API. The REST API Cognito authorizer has no OAuth scopes,
   *  so it validates ID tokens only; an access token gets 401. */
  apiToken(): Promise<string | null>;
}

export function createAmplifyAuth(config: RuntimeConfig): AuthService {
  Amplify.configure({
    Auth: { Cognito: { userPoolId: config.userPoolId, userPoolClientId: config.userPoolClientId } },
  });
  return {
    async currentUser() {
      try { return (await getCurrentUser()).username; } catch { return null; }
    },
    async signIn(username, password) {
      const r = await signIn({ username, password });
      if (!r.isSignedIn) throw new Error(`Additional sign-in step required: ${r.nextStep.signInStep}`);
    },
    signOut: () => signOut(),
    async apiToken() {
      const s = await fetchAuthSession();
      return s.tokens?.idToken?.toString() ?? null;
    },
  };
}
