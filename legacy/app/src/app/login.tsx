import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { useRequestCode, useVerifyCode } from '@/api/hooks';
import { ErrorNote, Field } from '@/components/Field';
import { PlainScreen } from '@/components/PlainScreen';
import { Txt } from '@/components/Txt';
import { PrimaryButton, SkipLink } from '@/components/ui';
import { colors } from '@/theme';

/**
 * Sign in with an email code. Separate from Instagram: Curo never asks for an Instagram
 * login or password (logic doc §3).
 */
export default function Login() {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const request = useRequestCode();
  const verify = useVerifyCode();

  const send = () =>
    request.mutate(email.trim(), {
      onSuccess: (r) => {
        setSentTo(email.trim());
        setDevCode(r.dev_code ?? null);
        setCode(r.dev_code ?? '');
      },
    });

  const signIn = () =>
    verify.mutate({ email: sentTo ?? email, code }, { onSuccess: () => router.replace('/') });

  return (
    <PlainScreen>
      <Txt size={20} weight={600}>
        Sign in
      </Txt>
      {sentTo ? (
        <>
          <Txt size={14.5} lh={1.55} color={colors.muted}>
            Enter the 6-digit code we sent to {sentTo}.
          </Txt>
          <Field
            label="Sign-in code"
            value={code}
            onChangeText={setCode}
            placeholder="6-digit code"
            keyboardType="number-pad"
            maxLength={6}
            onSubmitEditing={signIn}
          />
          {devCode ? (
            <Txt size={12.5} color={colors.muted}>
              Development build: there’s no email service yet, so your code is filled in.
            </Txt>
          ) : null}
          {verify.isError ? <ErrorNote text={verify.error.message} /> : null}
          <PrimaryButton
            label="Sign in"
            onPress={signIn}
            disabled={code.length !== 6 || verify.isPending}
          />
          <SkipLink label="Use a different email" onPress={() => setSentTo(null)} />
        </>
      ) : (
        <>
          <Txt size={14.5} lh={1.55} color={colors.muted}>
            We’ll email you a 6-digit code. No password — and Curo never asks for your Instagram
            login.
          </Txt>
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            onSubmitEditing={send}
          />
          {request.isError ? <ErrorNote text={request.error.message} /> : null}
          <PrimaryButton
            label="Send code"
            onPress={send}
            disabled={!email.includes('@') || request.isPending}
          />
        </>
      )}
      <View style={{ height: 8 }} />
    </PlainScreen>
  );
}
