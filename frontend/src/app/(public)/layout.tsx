import { HeartHandshake } from "lucide-react";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-muted/30">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-2xl items-center gap-2 px-4 py-4">
          <HeartHandshake className="size-5 text-primary" />
          <span className="font-semibold tracking-tight">Donate</span>
        </div>
      </header>
      <main className="flex flex-1 justify-center px-4 py-8 sm:py-12">
        <div className="w-full max-w-2xl">{children}</div>
      </main>
      <footer className="border-t bg-background py-6 text-center text-xs text-muted-foreground">
        Secured by Razorpay · Your information is used only to process this donation and issue your receipt.
      </footer>
    </div>
  );
}
