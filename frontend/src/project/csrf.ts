export function readCsrfToken(cookies: string, cookieName: string): string {
  const prefix = `${cookieName}=`;
  const cookie = cookies.split(";").map(value => value.trim()).find(value => value.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : "";
}
