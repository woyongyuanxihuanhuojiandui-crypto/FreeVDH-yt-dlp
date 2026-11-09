const CHANNEL = "freevdh-playback-session";
const STORAGE_KEY = "freevdhPlaybackSession";
let transition = Promise.resolve();

const readSession = async () => (await chrome.storage.session.get(STORAGE_KEY))[STORAGE_KEY];
const writeSession = session => chrome.storage.session.set({ [STORAGE_KEY]: session });
const sameSession = (left, right) => left && right
  && left.tabId === right.tabId
  && left.frameId === right.frameId
  && left.mediaId === right.mediaId;
const command = (session, action, state) => chrome.tabs.sendMessage(
  session.tabId,
  { channel: CHANNEL, action, mediaId: session.mediaId, state },
  { frameId: session.frameId },
);
const broadcast = session => new Promise(resolve => chrome.runtime.sendMessage(
  { channel: CHANNEL, event: "state", session },
  () => {
    void chrome.runtime.lastError;
    resolve();
  },
));

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message?.channel !== CHANNEL) return;
  if (message.event === "identify") {
    readSession().then(session => chrome.tabs.sendMessage(
      sender.tab.id,
      {
        channel: CHANNEL,
        event: "identify",
        context: { tabId: sender.tab.id, frameId: sender.frameId ?? 0 },
        session,
      },
      { frameId: sender.frameId ?? 0 },
    ));
    return;
  }
  if (sender.tab?.id == null) return;

  transition = transition.then(async () => {
    const current = await readSession();
    const source = {
      tabId: sender.tab.id,
      frameId: sender.frameId ?? 0,
      mediaId: message.mediaId,
    };

    if (message.event === "claim") {
      if (sameSession(current, source)) return;
      const next = { ...source, pip: false };
      await writeSession(next);
      if (current) await command(current, "stop");
      if (current && message.state?.paused === false) await command(next, "resume", message.state);
      await broadcast(next);
      return;
    }

    if (!sameSession(current, source)) return;
    if (message.event === "pip-enter" || message.event === "pip-leave") {
      const next = { ...current, pip: message.event === "pip-enter" };
      await writeSession(next);
      await broadcast(next);
    }
  });
  transition.then(() => respond({ ok: true }));
  return true;
});
