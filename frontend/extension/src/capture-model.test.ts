import { cropBox, dataUrlToBlob, isLocalServer, normalizeServer } from './capture-model';

it('crops in screenshot pixels and stays inside the screenshot', () => {
  // A 2x screen: the 1000 px wide viewport is 2000 px in the screenshot.
  expect(cropBox({ x: 10, y: 20, width: 100, height: 50 }, 1000, 2000, 1200)).toEqual({
    x: 20,
    y: 40,
    width: 200,
    height: 100,
  });
  expect(cropBox({ x: 950, y: 590, width: 100, height: 100 }, 1000, 1000, 600)).toEqual({
    x: 950,
    y: 590,
    width: 50,
    height: 10,
  });
});

it('accepts plain http(s) server origins and knows which are local', () => {
  expect(normalizeServer(' http://clearcontext.localhost/ ')).toBe('http://clearcontext.localhost');
  expect(normalizeServer('http://127.0.0.1:8080')).toBe('http://127.0.0.1:8080');
  for (const bad of ['ftp://x', 'http://u:p@host', 'http://host/app', 'http://host/?a=1', 'x']) {
    expect(normalizeServer(bad)).toBeNull();
  }
  expect(isLocalServer('http://clearcontext.localhost')).toBe(true);
  expect(isLocalServer('http://192.168.1.5:8080')).toBe(false);
});

it('turns a data URL back into a typed blob', async () => {
  const blob = dataUrlToBlob('data:image/jpeg;base64,/9j/');
  expect(blob.type).toBe('image/jpeg');
  // The JPEG start marker FF D8 FF.
  expect([...new Uint8Array(await blob.arrayBuffer())]).toEqual([0xff, 0xd8, 0xff]);
});
