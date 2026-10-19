export default function Layout({ children }: LayoutProps<"/p/[gtin]">) {
  return <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">{children}</div>;
}
