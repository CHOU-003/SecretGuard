import { useState } from 'react';
import TextField from './TextField.jsx';
import { LockIcon, EyeIcon, EyeOffIcon } from './icons.jsx';

export default function PasswordField(props) {
  const [visible, setVisible] = useState(false);
  const ToggleIcon = visible ? EyeOffIcon : EyeIcon;

  return (
    <TextField
      {...props}
      type={visible ? 'text' : 'password'}
      icon={LockIcon}
      rightSlot={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
          aria-pressed={visible}
          className="rounded-md p-1 text-fg-muted transition hover:text-fg focus-visible:outline-2 focus-visible:outline-brand-sky"
        >
          <ToggleIcon className="h-5 w-5" />
        </button>
      }
    />
  );
}