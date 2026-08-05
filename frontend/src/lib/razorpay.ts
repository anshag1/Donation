"use client";

/** Loads Razorpay's Checkout script on demand and opens the payment widget.
 * Client-only — never imported from a Server Component. */

const CHECKOUT_SCRIPT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

declare global {
  interface Window {
    Razorpay: new (options: RazorpayOptions) => { open: () => void };
  }
}

export interface RazorpaySuccessResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface RazorpayOptions {
  key: string;
  order_id: string;
  amount: number;
  currency: string;
  name: string;
  description?: string;
  prefill?: { name?: string; contact?: string; email?: string };
  theme?: { color?: string };
  handler: (response: RazorpaySuccessResponse) => void;
  modal?: { ondismiss?: () => void };
  config?: {
    display: {
      blocks: Record<string, { name: string; instruments: Array<{ method: string }> }>;
      sequence: string[];
      preferences: { show_default_blocks: boolean };
    };
  };
}

/** Surfaces UPI as its own entry in the Checkout sidebar, ahead of the
 * default blocks (cards, netbanking, wallet, pay later), which still show
 * because show_default_blocks stays true. */
export const UPI_FIRST_CHECKOUT_CONFIG: RazorpayOptions["config"] = {
  display: {
    blocks: {
      upi: {
        name: "Pay by UPI",
        instruments: [{ method: "upi" }],
      },
    },
    sequence: ["block.upi"],
    preferences: { show_default_blocks: true },
  },
};

let scriptLoadPromise: Promise<void> | null = null;

function loadCheckoutScript(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Razorpay Checkout can only be loaded in the browser"));
  }
  if (window.Razorpay) {
    return Promise.resolve();
  }
  if (!scriptLoadPromise) {
    scriptLoadPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = CHECKOUT_SCRIPT_SRC;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Could not load Razorpay Checkout. Check your connection."));
      document.body.appendChild(script);
    });
  }
  return scriptLoadPromise;
}

export async function openRazorpayCheckout(options: RazorpayOptions): Promise<void> {
  await loadCheckoutScript();
  const checkout = new window.Razorpay(options);
  checkout.open();
}
