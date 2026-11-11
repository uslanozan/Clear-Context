import { assetUrl, demoFile } from '../lib/demo';

const id = '67650b41-29fd-4d77-bbc7-477e141f4b85';

it('answers demo reads from recorded files under the base path', () => {
  expect(demoFile('/health')).toBe('/data/health.json');
  expect(demoFile('/prices')).toBe('/data/prices.json');
  expect(demoFile('/groups')).toBe('/data/groups.json');
  expect(demoFile('/investigations?limit=20&offset=0')).toBe('/data/history.json');
  expect(demoFile(`/investigations/${id}`)).toBe(`/data/investigations/${id}.json`);
  expect(demoFile(`/investigations/${id}/report`)).toBe(`/data/investigations/${id}/report.json`);
  expect(demoFile(`/investigations/${id}/steps`)).toBe(`/data/investigations/${id}/steps.json`);
});

it('has one history page and nothing else', () => {
  expect(demoFile('/investigations?limit=20&offset=20')).toEqual([]);
  expect(demoFile('/settings')).toBeNull();
  // Only investigation IDs map to files, so a path cannot reach another folder.
  expect(demoFile('/investigations/../settings')).toBeNull();
});

it('serves public files from the base path', () => {
  expect(assetUrl('/brand/meta.svg')).toBe('/brand/meta.svg');
  expect(assetUrl('brand/meta.svg')).toBe('/brand/meta.svg');
});
