/**
 * Keep profile failures visible without treating a temporary backend error as
 * an access-list denial. Never include tokens or raw server errors in messages.
 */
export async function fetchSessionProfile(url, token, request = fetch) {
  try {
    const response = await request(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.status === 403) {
      const body = await response.json().catch(() => null);
      return {
        user: null,
        denied: typeof body?.detail === "string"
          ? body.detail
          : "This account isn't on the wedding's access list yet. Ask the couple to add you, then sign in again.",
        error: null,
      };
    }
    if (response.status === 401) {
      return {
        user: null,
        denied: null,
        error: "We couldn't verify your sign-in. Please sign in again. If this continues, the app's sign-in service needs attention.",
      };
    }
    if (!response.ok) {
      return {
        user: null,
        denied: null,
        error: "The app couldn't complete sign-in. Please try again shortly.",
      };
    }
    const user = await response.json();
    if (!user || typeof user.id !== "string" || typeof user.role !== "string") {
      return {
        user: null,
        denied: null,
        error: "The app returned an incomplete sign-in response. Please try again.",
      };
    }
    return { user, denied: null, error: null };
  } catch {
    return {
      user: null,
      denied: null,
      error: "We couldn't reach the sign-in service. Check your connection and try again.",
    };
  }
}
