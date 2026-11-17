import type { InputHTMLAttributes } from 'react';

type Props = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'value' | 'onChange'
> & {
  value: string;
  mask: string;
  onChange: (value: string) => void;
};
export function formatDigits(value: string, mask: string) {
  const digits = value.replace(/\D/g, '');
  let result = '',
    index = 0;
  for (const char of mask) {
    if (index >= digits.length) break;
    result += char === '#' ? digits[index++] : char;
  }
  return result;
}
function caretAfterDigits(text: string, count: number) {
  let index = 0,
    seen = 0;
  while (index < text.length && seen < count) {
    if (/\d/.test(text[index])) seen++;
    index++;
  }
  return index;
}
export function MaskedInput({ value, mask, onChange, ...props }: Props) {
  const limit = (mask.match(/#/g) || []).length;
  const formatted = formatDigits(value, mask);
  return (
    <input
      {...props}
      inputMode="numeric"
      value={formatted}
      minLength={mask.length}
      maxLength={mask.length}
      onChange={(event) => {
        const input = event.currentTarget;
        const count = input.value
          .slice(0, input.selectionStart || 0)
          .replace(/\D/g, '').length;
        const digits = input.value.replace(/\D/g, '').slice(0, limit);
        onChange(digits);
        const next = formatDigits(digits, mask);
        // Restore the caret after React adds punctuation, including edits in the middle.
        requestAnimationFrame(() => {
          if (document.activeElement === input) {
            const caret = caretAfterDigits(next, count);
            input.setSelectionRange(caret, caret);
          }
        });
      }}
      onKeyDown={(event) => {
        const input = event.currentTarget;
        const start = input.selectionStart || 0;
        if (props.readOnly || input.selectionEnd !== start) return;
        const back = event.key === 'Backspace';
        if (!back && event.key !== 'Delete') return;
        const adjacent = formatted[back ? start - 1 : start];
        if (!adjacent || /\d/.test(adjacent)) return;
        event.preventDefault();
        const before = formatted.slice(0, start).replace(/\D/g, '').length;
        const index = back ? before - 1 : before;
        const next = value.slice(0, index) + value.slice(index + 1);
        onChange(next);
        requestAnimationFrame(() => {
          const caret = caretAfterDigits(
            formatDigits(next, mask),
            Math.max(0, index),
          );
          input.setSelectionRange(caret, caret);
        });
      }}
    />
  );
}
