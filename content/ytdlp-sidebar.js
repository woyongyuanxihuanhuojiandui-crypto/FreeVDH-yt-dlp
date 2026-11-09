(() => {
  const host = 'com.freevdh.ytdlp';
  const status = document.createElement('div');
  status.role = 'status';
  status.hidden = true;
  status.style.cssText = 'position:fixed;bottom:8px;left:8px;right:8px;z-index:2147483647;padding:10px;background:var(--theme-box-bg);color:inherit;border:1px solid var(--theme-box-border);border-radius:8px;box-shadow:0 2px 10px #0003;font-size:13px';
  document.body.append(status);
  let timer;
  const show = (text, timeout = 0) => {
    clearTimeout(timer);
    status.textContent = text;
    status.hidden = false;
    if (timeout) timer = setTimeout(() => status.hidden = true, timeout);
  };
  const request = payload => new Promise((resolve, reject) => {
    const port = chrome.runtime.connectNative(host);
    port.onMessage.addListener(message => {
      port.disconnect();
      message.state === 'error' ? reject(new Error(message.message)) : resolve(message);
    });
    port.onDisconnect.addListener(() => chrome.runtime.lastError && reject(new Error(chrome.runtime.lastError.message)));
    port.postMessage(payload);
  });
  window.freeVDHYtdlpRequest = payload => request(payload).catch(error => show(error.message, 8000));
  window.freeVDHYtdlpDownload = async card => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.url || !/^https?:\/\//i.test(tab.url)) throw new Error('请先打开视频网页。');
      card.dataset.sidebarYtdlp = 'true';
      const port = chrome.runtime.connectNative(host);
      let finished = false;
      let stopping = false;
      const stopDownload = () => {
        stopping = true;
        port.postMessage({ action: 'stop' });
        card.sidebarSetDownloadIdle();
      };
      card.sidebarSetDownloadProgress(undefined, stopDownload);
      port.onMessage.addListener(message => {
        if (message.state === 'downloading' && !stopping) card.sidebarSetDownloadProgress(message.percent);
        if (message.state === 'stopped') {
          finished = true;
          delete card.dataset.sidebarYtdlp;
          card.sidebarSetDownloadIdle();
          port.disconnect();
        }
        if (message.state === 'done' || message.state === 'error') {
          finished = true;
          if (message.state === 'done') {
            window.freeVDHYtdlpHistory.add({
              path: message.path,
              name: message.path.split(/[\\/]/).pop(),
              url: tab.url,
              timestamp: Date.now(),
            });
            card.sidebarSetDownloadComplete({
            open: () => window.freeVDHYtdlpRequest({ action: 'show', path: message.path }),
            remove: () => request({ action: 'delete', path: message.path }).then(() => {
              window.freeVDHYtdlpHistory.remove(message.path);
              delete card.dataset.sidebarYtdlp;
              card.sidebarSetDownloadIdle();
            }).catch(error => show(error.message, 8000)),
          });
          } else {
            delete card.dataset.sidebarYtdlp;
            card.sidebarSetDownloadIdle();
            show('下载失败：' + message.message, 8000);
          }
          port.disconnect();
        }
      });
      port.onDisconnect.addListener(() => {
        if (!finished && !stopping) {
          delete card.dataset.sidebarYtdlp;
          card.sidebarSetDownloadIdle();
          show('未检测到 FreeVDH-yt-dlp 桥接组件，请先运行压缩包中的安装程序。', 8000);
        } else if (stopping) {
          delete card.dataset.sidebarYtdlp;
          card.sidebarSetDownloadIdle();
        }
      });
      port.postMessage({ action: 'download', url: tab.url });
    } catch (error) {
      delete card.dataset.sidebarYtdlp;
      card.sidebarSetDownloadIdle();
      show(error.message, 8000);
    }
  };
})();
