import type { Speech } from "./hearing";

export const SYNTH_MS = 8000;
export const PLAY_MS = 60000;

type Synth = (speaker: string, text: string) => Promise<{ audio: string; content_type: string }>;

/** Plays court speeches with Amazon Polly voices. Each speech is synthesised once per page
 * (cached by speaker and text); a new speech stops the one playing. */
export function createVoice(synth: Synth, makeAudio: (src: string) => HTMLAudioElement = (src) => new Audio(src)) {
  const cache = new Map<string, Promise<string>>();
  let playing: HTMLAudioElement | null = null;
  async function speak(speech: Speech): Promise<void> {
    const key = `${speech.speaker}|${speech.text}`;
    if (!cache.has(key)) {
      cache.set(key, synth(speech.speaker, speech.text.slice(0, 600))
        .then((r) => `data:${r.content_type};base64,${r.audio}`)
        .catch((e) => { cache.delete(key); throw e; }));
    }
    // A slow or failed voice must never hold the hearing back: give up after SYNTH_MS and move on.
    const src = await Promise.race([cache.get(key)!, new Promise<null>((r) => setTimeout(() => r(null), SYNTH_MS))]);
    playing?.pause();
    if (src === null) return;
    const audio = makeAudio(src);
    playing = audio;
    await new Promise<void>((resolve) => {
      const guard = setTimeout(resolve, PLAY_MS); // a clip that never reports its end
      const done = () => { clearTimeout(guard); resolve(); };
      audio.onended = done;
      audio.onerror = done;
      audio.onpause = done;
      void audio.play().catch(done); // autoplay refused or decoding failed: carry on in silence
    });
  }
  /** Stop the clip that is playing (sound switched off, or the hearing left). */
  speak.stop = () => { playing?.pause(); playing = null; };
  return speak;
}
