"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { AmountPicker } from "@/components/donation/AmountPicker";
import { apiClient, ApiError } from "@/lib/api-client";
import { formatInrFromPaise } from "@/lib/format";
import { openRazorpayCheckout } from "@/lib/razorpay";
import type { DonationInitiateResponse, PublicEvent } from "@/types/api";

const MIN_AMOUNT_IN_PAISE = 100;
const MAX_AMOUNT_IN_PAISE = 10_000_000_00;

const donorSchema = z.object({
  full_name: z.string().trim().min(2, "Enter your full name").max(200, "That name looks too long"),
  mobile_number: z
    .string()
    .trim()
    .transform((v) => v.replace(/[\s-]/g, ""))
    .refine((v) => /^\+?[0-9]{10,13}$/.test(v), "Enter a valid mobile number"),
  email: z
    .string()
    .trim()
    .optional()
    .refine((v) => !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v), "Enter a valid email address"),
  pan_number: z
    .string()
    .trim()
    .optional()
    .refine((v) => !v || /^[A-Za-z]{5}[0-9]{4}[A-Za-z]$/.test(v), "Enter a valid PAN, e.g. ABCDE1234F"),
  address: z.string().trim().max(500).optional(),
});

type DonorFormValues = z.infer<typeof donorSchema>;

interface DonationFormProps {
  event?: PublicEvent;
  organizationName?: string;
}

export function DonationForm({ event, organizationName = "Our Organization" }: DonationFormProps) {
  const router = useRouter();
  const [amountInPaise, setAmountInPaise] = useState<number | null>(null);
  const [customAmountInput, setCustomAmountInput] = useState("");
  const [amountError, setAmountError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<DonorFormValues>({
    resolver: zodResolver(donorSchema),
  });

  const onSubmit = async (donor: DonorFormValues) => {
    if (!amountInPaise || amountInPaise < MIN_AMOUNT_IN_PAISE) {
      setAmountError("Please select or enter a donation amount");
      return;
    }
    if (amountInPaise > MAX_AMOUNT_IN_PAISE) {
      setAmountError("That amount is larger than we can process online — please contact us directly");
      return;
    }
    setAmountError(null);
    setIsSubmitting(true);

    try {
      const initiateResponse = await apiClient.post<DonationInitiateResponse>(
        "/api/v1/donations/initiate",
        {
          event_id: event?.id ?? null,
          donor: {
            full_name: donor.full_name,
            mobile_number: donor.mobile_number,
            email: donor.email || undefined,
            pan_number: donor.pan_number || undefined,
            address: donor.address || undefined,
          },
          amount_in_paise: amountInPaise,
          purpose: event?.title,
        },
      );

      await openRazorpayCheckout({
        key: initiateResponse.razorpay_key_id,
        order_id: initiateResponse.razorpay_order_id,
        amount: initiateResponse.amount_in_paise,
        currency: initiateResponse.currency,
        name: organizationName,
        description: event?.title ?? "Donation",
        prefill: {
          name: donor.full_name,
          contact: donor.mobile_number,
          email: donor.email,
        },
        theme: { color: "#4338ca" },
        handler: (response) => {
          apiClient
            .post("/api/v1/donations/" + initiateResponse.donation_id + "/client-callback", {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              client_status: "success",
            })
            .catch(() => {
              /* informational only — the webhook is the source of truth */
            });
          router.push(`/donate/confirmation/${initiateResponse.donation_id}`);
        },
        modal: {
          ondismiss: () => {
            setIsSubmitting(false);
            toast.info("Payment window closed", {
              description: "No amount was charged. You can try again whenever you're ready.",
            });
          },
        },
      });
    } catch (error) {
      setIsSubmitting(false);
      const message =
        error instanceof ApiError
          ? error.message
          : "We couldn't start your donation. Please check your connection and try again.";
      toast.error("Something went wrong", { description: message });
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" noValidate>
      <div className="space-y-3">
        <Label className="text-base">Choose an amount</Label>
        <AmountPicker
          valueInPaise={amountInPaise}
          onChange={(value) => {
            setAmountInPaise(value);
            setAmountError(null);
          }}
          customAmountInput={customAmountInput}
          onCustomAmountInputChange={setCustomAmountInput}
        />
        {amountError && <p className="text-sm text-destructive">{amountError}</p>}
      </div>

      <Separator />

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="full_name">Full name</Label>
          <Input id="full_name" placeholder="As you'd like it on your receipt" {...register("full_name")} />
          {errors.full_name && <p className="text-sm text-destructive">{errors.full_name.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="mobile_number">Mobile number</Label>
          <Input id="mobile_number" inputMode="tel" placeholder="98765 43210" {...register("mobile_number")} />
          {errors.mobile_number && (
            <p className="text-sm text-destructive">{errors.mobile_number.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="email">
            Email <span className="text-muted-foreground font-normal">(optional)</span>
          </Label>
          <Input id="email" type="email" placeholder="you@example.com" {...register("email")} />
          {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="pan_number">
            PAN <span className="text-muted-foreground font-normal">(optional, for 80G receipt)</span>
          </Label>
          <Input
            id="pan_number"
            placeholder="ABCDE1234F"
            className="uppercase placeholder:normal-case"
            {...register("pan_number")}
          />
          {errors.pan_number && <p className="text-sm text-destructive">{errors.pan_number.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="address">
            Address <span className="text-muted-foreground font-normal">(optional)</span>
          </Label>
          <Input id="address" placeholder="City, State" {...register("address")} />
        </div>
      </div>

      <Button
        type="submit"
        disabled={isSubmitting}
        className="w-full bg-brand text-brand-foreground hover:bg-brand/90 h-11 text-base font-semibold"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="animate-spin" /> Processing…
          </>
        ) : amountInPaise ? (
          `Donate ${formatInrFromPaise(amountInPaise)}`
        ) : (
          "Donate now"
        )}
      </Button>

      <p className="text-center text-xs text-muted-foreground">
        Payments are processed securely by Razorpay. We never see or store your card details.
      </p>
    </form>
  );
}
