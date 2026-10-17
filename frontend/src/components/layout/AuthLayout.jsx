import Logo from '../common/Logo.jsx';

export default function AuthLayout({ children }) {
  return (
    <div className="auth-bg flex min-h-screen flex-col font-auth text-fg">
      <header className="px-6 pt-8 sm:px-12 lg:px-18">
        <Logo />
      </header>
      <main className="mx-auto grid w-full max-w-5xl flex-1 items-center gap-10 px-6 py-10 lg:grid-cols-[1fr_484px] lg:gap-16">
        {children}
      </main>
    </div>
  );
}