/** Currency/date display formatting — always go through here, never inline
 * `₹${amount}` (see docs/05-architecture.md coding standards). */

export function formatInrFromPaise(amountInPaise: number): string {
  const rupees = amountInPaise / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: rupees % 1 === 0 ? 0 : 2,
  }).format(rupees);
}

export function rupeesToPaise(rupees: number): number {
  return Math.round(rupees * 100);
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(iso));
}
