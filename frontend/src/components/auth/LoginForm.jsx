import Logo from '../common/Logo.jsx';
import TextField from '../common/TextField.jsx';
import PasswordField from '../common/PasswordField.jsx';
import Button from '../common/Button.jsx';
import Alert from '../common/Alert.jsx';
import { UserIcon, LoginIcon } from '../common/icons.jsx';
import { useLoginForm } from '../../hooks/useLoginForm.js';

export default function LoginForm() {
  const { username, setUsername, password, setPassword, error, loading, handleSubmit } =
    useLoginForm();

  return (
    <section className="mx-auto w-full max-w-121 rounded-2xl border border-edge bg-[#061038]/60 p-8 shadow-[0_0_60px_-12px_rgba(70,80,255,0.4)] backdrop-blur-sm">
      <Logo />
      <h2 className="mt-6 text-3xl font-semibold tracking-tight text-fg">Đăng nhập</h2>

      <form onSubmit={handleSubmit} className="mt-7 space-y-5">
        <TextField
          id="username"
          label="Tên đăng nhập"
          icon={UserIcon}
          type="text"
          autoComplete="username"
          placeholder="Nhập tên đăng nhập của bạn"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />

        <PasswordField
          id="password"
          label="Mật khẩu"
          autoComplete="current-password"
          placeholder="Nhập mật khẩu"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <Alert>{error}</Alert>

        <Button type="submit" icon={LoginIcon} loading={loading}>
          {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
        </Button>
      </form>
    </section>
  );
}