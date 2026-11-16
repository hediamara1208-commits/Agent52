// Guest access for the public demonstration: no account, one random 128-bit id per browser.
// The Session_API files every hearing under that id, so two visitors never see each other's cases.
const KEY = "verdict.guest";
let memory: string | null = null;

function fresh(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function guestId(): string {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved && /^[0-9a-f]{32}$/.test(saved)) return saved;
    const id = fresh();
    localStorage.setItem(KEY, id);
    return id;
  } catch {
    return (memory ??= fresh()); // private mode without storage: the id lasts for this page
  }
}

/** Value of the Authorization header the Session_API accepts from a guest. */
export const guestToken = async () => `Guest ${guestId()}`;
