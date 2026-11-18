export function shouldSubmit(event: Pick<KeyboardEvent, 'key' | 'shiftKey' | 'isComposing'> & { keyCode?: number }, composing = false) {
  return event.key === 'Enter' && !event.shiftKey && !event.isComposing && !composing && event.keyCode !== 229
}
