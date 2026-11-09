(() => {
  const SESSION_CHANNEL = "freevdh-playback-session";
  const mediaIds = new WeakMap();
  const mediaById = new Map();
  const pipPlayback = new WeakMap();
  const watchedVideos = new WeakSet();
  let nextMediaId = 1;
  let pageContext;
  let activeSession;
  let pipElement;

  const idFor = media => {
    if (!mediaIds.has(media)) {
      mediaIds.set(media, nextMediaId);
      mediaById.set(nextMediaId, media);
      nextMediaId++;
    }
    return mediaIds.get(media);
  };
  const currentMedia = mediaId => {
    const media = [...document.querySelectorAll("video, audio")];
    return { media, current: mediaById.get(mediaId) || media.find(item => !item.paused) || media[0] };
  };
  const mediaState = (media, count = 1) => ({
    count,
    mediaId: idFor(media),
    paused: media.paused,
    loop: media.loop,
    muted: media.muted,
    volume: media.volume,
    speed: media.playbackRate,
    currentTime: media.currentTime,
    duration: Number.isFinite(media.duration) ? media.duration : 0,
    kind: media.tagName.toLowerCase(),
    pip: pipElement === media,
    fullscreen: document.fullscreenElement === media,
  });
  const applyState = (media, state) => {
    media.loop = state.loop;
    media.muted = state.muted;
    media.volume = state.volume;
    media.playbackRate = state.speed;
    media.currentTime = state.currentTime;
  };
  const sameActiveMedia = media => activeSession
    && pageContext
    && activeSession.tabId === pageContext.tabId
    && activeSession.frameId === pageContext.frameId
    && activeSession.mediaId === idFor(media);
  const claimMedia = (media, playing = !media.paused) => {
    const state = mediaState(media);
    state.paused = !playing;
    const replacing = activeSession && !sameActiveMedia(media);
    if (pageContext) activeSession = { ...pageContext, mediaId: idFor(media) };
    if (replacing) media.pause();
    chrome.runtime.sendMessage({
      channel: SESSION_CHANNEL,
      event: "claim",
      mediaId: idFor(media),
      state,
    });
    return replacing;
  };
  const primaryVideo = () => [...document.querySelectorAll("video")]
    .sort((left, right) => right.clientWidth * right.clientHeight - left.clientWidth * left.clientHeight)[0];
  const runSessionCommand = async message => {
    const media = mediaById.get(message.mediaId);
    if (message.action === "stop") {
      closeProjection();
      pipPlayback.set(media, false);
      media.pause();
      if (document.pictureInPictureElement === media) await document.exitPictureInPicture();
    }
    if (message.action === "resume") {
      applyState(media, message.state);
      message.state.paused ? media.pause() : await media.play();
    }
    return mediaState(media);
  };

  let projectionPeer;
  let projectionStream;
  let projectionMediaId;
  const waitForIce = peer => peer.iceGatheringState === "complete"
    ? Promise.resolve()
    : new Promise(resolve => {
      const complete = () => {
        if (peer.iceGatheringState !== "complete") return;
        peer.removeEventListener("icegatheringstatechange", complete);
        resolve();
      };
      peer.addEventListener("icegatheringstatechange", complete);
    });
  const closeProjection = () => {
    projectionPeer?.close();
    projectionStream?.getTracks().forEach(track => track.stop());
    projectionPeer = undefined;
    projectionStream = undefined;
    projectionMediaId = undefined;
  };
  const openProjection = async media => {
    closeProjection();
    projectionStream = media.captureStream();
    projectionPeer = new RTCPeerConnection({ iceServers: [] });
    projectionMediaId = idFor(media);
    projectionPeer.addTrack(projectionStream.getVideoTracks()[0], projectionStream);
    await projectionPeer.setLocalDescription(await projectionPeer.createOffer());
    await waitForIce(projectionPeer);
    return {
      mediaId: projectionMediaId,
      description: {
        type: projectionPeer.localDescription.type,
        sdp: projectionPeer.localDescription.sdp,
      },
    };
  };
  const answerProjection = async ({ mediaId, description }) => {
    if (mediaId !== projectionMediaId) return;
    await projectionPeer.setRemoteDescription(description);
  };

  chrome.runtime.onMessage.addListener((message, _sender, respond) => {
    if (message?.channel === SESSION_CHANNEL) {
      if (message.event === "identify") {
        pageContext = message.context;
        activeSession = message.session;
        return;
      }
      if (message.event === "state") {
        activeSession = message.session;
        return;
      }
      runSessionCommand(message).then(respond);
      return true;
    }
    if (message?.channel !== "freevdh-page-media") return;
    if (message.action === "projection-stop") {
      closeProjection();
      respond({ ok: true });
      return;
    }

    const { media, current } = currentMedia();
    if (!current) {
      respond({ count: 0 });
      return;
    }

    if (message.action === "projection-offer") {
      openProjection(current).then(respond, () => {
        closeProjection();
        respond({ unsupported: true });
      });
      return true;
    }
    if (message.action === "projection-answer") {
      answerProjection(message.value).then(() => respond({ ok: true }));
      return true;
    }

    if (["state", "peek", "handoff", "resume"].includes(message.action)) {
      if (message.action === "resume") {
        current.loop = message.value.loop;
        current.muted = message.value.muted;
        current.volume = message.value.volume;
        current.playbackRate = message.value.speed;
        current.currentTime = message.value.currentTime;
        message.value.paused ? current.pause() : current.play();
      }
      respond(mediaState(current, media.length));
      if (message.action === "handoff") current.pause();
      return;
    }

    if (message.action === "play" && !claimMedia(current, true)) current.play();
    if (message.action === "pause") current.pause();
    if (message.action === "speed") current.playbackRate = message.value;
    if (message.action === "loop") current.loop = message.value;
    if (message.action === "muted") current.muted = message.value;
    if (message.action === "volume") current.volume = message.value;
    if (message.action === "seek") current.currentTime = message.value;
    if (message.action === "pip") {
      document.pictureInPictureElement
        ? document.exitPictureInPicture()
        : current.requestPictureInPicture();
    }
    if (message.action === "fullscreen") {
      document.fullscreenElement ? document.exitFullscreen() : current.requestFullscreen();
    }
    if (message.action === "screenshot") {
      const canvas = document.createElement("canvas");
      canvas.width = current.videoWidth;
      canvas.height = current.videoHeight;
      canvas.getContext("2d").drawImage(current, 0, 0);
      const link = document.createElement("a");
      link.href = canvas.toDataURL("image/jpeg");
      link.download = `${location.hostname}-${Math.floor(current.currentTime)}.jpg`;
      link.click();
    }

    respond({ ok: true });
  });

  chrome.runtime.sendMessage({ channel: SESSION_CHANNEL, event: "identify" });
  const watchVideo = media => {
    if (watchedVideos.has(media)) return;
    watchedVideos.add(media);
    media.addEventListener("play", () => {
    if (media !== primaryVideo()) return;
    if (!navigator.userActivation.isActive && (media.muted || media.volume === 0)) return;
    claimMedia(media, true);
    });
  };
  document.querySelectorAll("video").forEach(watchVideo);
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node instanceof HTMLVideoElement) watchVideo(node);
    else if (node instanceof Element) node.querySelectorAll("video").forEach(watchVideo);
  }))).observe(document, { childList: true, subtree: true });
  setInterval(() => {
    const pip = document.documentElement.dataset.freevdhPip === "1";
    if (pip === Boolean(pipElement)) return;
    if (pip) {
      pipElement = currentMedia().current;
      pipPlayback.set(pipElement, !pipElement.paused);
      chrome.runtime.sendMessage({
        channel: SESSION_CHANNEL,
        event: "pip-enter",
        mediaId: idFor(pipElement),
      });
      return;
    }
    const previous = pipElement;
    pipElement = undefined;
    if (pipPlayback.get(previous) && previous.paused) previous.play();
    chrome.runtime.sendMessage({
      channel: SESSION_CHANNEL,
      event: "pip-leave",
      mediaId: idFor(previous),
    });
  }, 100);
})();
