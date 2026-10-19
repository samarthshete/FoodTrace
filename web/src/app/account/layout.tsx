export default function Layout({ children }: LayoutProps<"/account">) {
  return <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6">{children}</div>;
}
