import type { Speech } from "./hearing";

type Synth = (speaker: string, text: string) => Promise<{ audio: string; content_type: string }>;

/** Plays court speeches with Amazon Polly voices. Each speech is synthesised once per page
 * (cached by speaker and text); a new speech stops the one playing. */
export function createVoice(synth: Synth, makeAudio: (src: string) => HTMLAudioElement = (src) => new Audio(src)) {
  const cache = new Map<string, Promise<string>>();
  let playing: HTMLAudioElement | null = null;
  return async function speak(speech: Speech): Promise<void> {
    const key = `${speech.speaker}|${speech.text}`;
    if (!cache.has(key)) {
      cache.set(key, synth(speech.speaker, speech.text.slice(0, 600))
        .then((r) => `data:${r.content_type};base64,${r.audio}`)
        .catch((e) => { cache.delete(key); throw e; }));
    }
    const src = await cache.get(key)!;
    playing?.pause();
    const audio = makeAudio(src);
    playing = audio;
    await new Promise<void>((resolve) => {
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
      void audio.play().catch(() => resolve());
    });
  };
}
