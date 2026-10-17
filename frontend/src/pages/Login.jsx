import AuthLayout from '../components/layout/AuthLayout.jsx';
import LoginHero from '../components/auth/LoginHero.jsx';
import LoginForm from '../components/auth/LoginForm.jsx';

export default function Login() {
  return (
    <AuthLayout>
      <LoginHero />
      <LoginForm />
    </AuthLayout>
  );
}