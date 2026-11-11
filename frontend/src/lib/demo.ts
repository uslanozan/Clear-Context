/**
 * The static demo build (`vite build --mode demo`) shows recorded reports read from JSON files
 * next to it. It has no server, so it starts nothing and saves nothing.
 */
export const DEMO = import.meta.env.MODE === 'demo';
export const DOWNLOAD_URL = 'https://github.com/uslanozan/Clear-Context/releases/latest';
export const DEMO_READ_ONLY =
  'This demo only shows recorded reports. Download Clear Context to check your own claims.';

/** A file from public/, under the base path the app is served from (/demo/ for the demo). */
export function assetUrl(path: string): string {
  return import.meta.env.BASE_URL + path.replace(/^\//, '');
}

/** The demo file that answers a GET request, `[]` for pages past the first, or null. */
export function demoFile(path: string): string | [] | null {
  const [route, query = ''] = path.split('?');
  const data = assetUrl('data/');
  if (route === '/health' || route === '/prices' || route === '/groups') {
    return `${data}${route.slice(1)}.json`;
  }
  if (route === '/investigations') {
    const offset = new URLSearchParams(query).get('offset');
    return offset && offset !== '0' ? [] : `${data}history.json`;
  }
  const match = route.match(/^\/investigations\/([0-9a-f-]{36})(?:\/(steps|research|report))?$/);
  if (match) return `${data}investigations/${match[1]}${match[2] ? `/${match[2]}` : ''}.json`;
  return null;
}
