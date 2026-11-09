(() => {
  let pip = false;
  setInterval(() => {
    const current = Boolean(document.pictureInPictureElement);
    if (current === pip) return;
    pip = current;
    document.documentElement.dataset.freevdhPip = pip ? "1" : "0";
  }, 100);
})();
