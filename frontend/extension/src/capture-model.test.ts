import { cropBox, dataUrlToBlob } from './capture-model';

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

it('turns a data URL back into a typed blob', async () => {
  const blob = dataUrlToBlob('data:image/jpeg;base64,/9j/');
  expect(blob.type).toBe('image/jpeg');
  // The JPEG start marker FF D8 FF.
  expect([...new Uint8Array(await blob.arrayBuffer())]).toEqual([0xff, 0xd8, 0xff]);
});
