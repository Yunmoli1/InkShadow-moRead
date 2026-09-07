/** TTS via Web Speech API, with rate/pitch controls. */

export const tts = {
  supported(): boolean {
    return 'speechSynthesis' in window
  },

  voices(): SpeechSynthesisVoice[] {
    return window.speechSynthesis.getVoices()
  },

  speak(text: string, opts: { rate?: number; pitch?: number; voiceURI?: string; onend?: () => void } = {}) {
    if (!this.supported()) return
    this.stop()
    // chunk long text (browsers cut off long utterances)
    const chunks = text.match(/[^。！？\n]{1,120}[。！？\n]?/g) ?? [text]
    chunks.forEach((chunk, i) => {
      const u = new SpeechSynthesisUtterance(chunk)
      u.lang = 'zh-CN'
      u.rate = opts.rate ?? 1
      u.pitch = opts.pitch ?? 1
      if (opts.voiceURI) {
        const v = this.voices().find((v) => v.voiceURI === opts.voiceURI)
        if (v) u.voice = v
      }
      if (i === chunks.length - 1 && opts.onend) u.onend = opts.onend
      window.speechSynthesis.speak(u)
    })
  },

  pause() { window.speechSynthesis.pause() },
  resume() { window.speechSynthesis.resume() },
  stop() { window.speechSynthesis.cancel() },
}
