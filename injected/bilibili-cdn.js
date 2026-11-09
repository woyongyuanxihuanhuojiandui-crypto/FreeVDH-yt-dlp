globalThis.freeVDHBilibiliMediaUrl = media => {
  const primary = media.url ?? media.baseUrl ?? media.base_url;
  return [...(media.backupUrl ?? media.backup_url ?? []), primary].find(value => {
    const url = new URL(value);
    return url.protocol === "https:" && (!url.port || url.port === "443");
  }) ?? primary;
};

globalThis.freeVDHBilibiliFingerprint = () => {
  const randomText = length => btoa(Array.from(
    { length },
    () => String.fromCharCode(33 + Math.floor(Math.random() * 94)),
  ).join("")).slice(0, -2);
  const width = globalThis.screen?.width || 1920;
  const height = globalThis.screen?.height || 1080;
  const whRandom = Math.floor(Math.random() * 114);
  const scrollTop = Math.floor(Math.random() * 101);
  const ofRandom = Math.floor(Math.random() * 514);
  return {
    dm_img_list: "[]",
    dm_img_str: randomText(32),
    dm_cover_img_str: randomText(64),
    dm_img_inter: JSON.stringify({
      ds: [],
      wh: [2 * width + 2 * height + 3 * whRandom, 4 * width - height + whRandom, whRandom],
      of: [3 * scrollTop + ofRandom, 4 * scrollTop + 2 * ofRandom, ofRandom],
    }),
  };
};
