'use client';
/** v2.1: onboarding starts at /start (username first, then the three cards at /welcome). */
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function Onboarding() {
  const router = useRouter();
  useEffect(() => router.replace('/start'), [router]);
  return null;
}
