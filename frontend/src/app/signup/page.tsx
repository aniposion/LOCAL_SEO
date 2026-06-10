'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { MapPin, Loader2, Mail, Lock, User } from 'lucide-react';
import { getApiErrorMessage } from '@/lib/api-errors';
import { useAuthStore } from '@/store/auth';
import { authApi, billingApi } from '@/lib/api';
import { toast } from 'sonner';

const signupCopy = {
  title: 'Start your free preview',
  subtitle: 'Get a free Google Maps audit, then review the fix plan. No credit card required.',
  nameLabel: 'Full Name',
  namePlaceholder: 'Jane Kim',
  emailLabel: 'Email',
  emailPlaceholder: 'you@example.com',
  passwordLabel: 'Password',
  passwordPlaceholder: 'At least 8 characters',
  button: 'Create account',
  loading: 'Creating your account...',
  divider: 'Or sign up with',
  google: 'Continue with Google',
  terms: 'By signing up, you agree to our',
  termsLink: 'Terms',
  privacyLink: 'Privacy Policy',
  loginPrompt: 'Already have an account?',
  loginLink: 'Sign in',
  fieldError: 'Please fill in all required fields.',
  passwordError: 'Password must be at least 8 characters.',
};

function SignupInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get('redirect');
  const { login } = useAuthStore();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName || !email || !password) {
      toast.error(signupCopy.fieldError);
      return;
    }

    if (password.length < 8) {
      toast.error(signupCopy.passwordError);
      return;
    }

    setIsLoading(true);
    try {
      const response = await authApi.register({
        email,
        password,
        full_name: fullName,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
        language: 'en',
        accept_terms: true,
        accept_privacy: true,
      });
      const { access_token, user } = response.data;
      login(access_token, user);
      toast.success("Account created. Let's find your business.");

      if (redirect === 'trial') {
        try {
          await billingApi.startTrial('free');
        } catch {
          toast.message('Your free account is ready. Paid features stay locked until you choose a plan.');
        }
        router.push('/dashboard?trial=true');
      } else if (redirect?.startsWith('/')) {
        router.push(redirect);
      } else {
        router.push('/onboarding');
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, signupCopy.fieldError));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="w-10 h-10 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center">
            <MapPin className="w-6 h-6 text-white" />
          </div>
          <span className="font-bold text-2xl">Local SEO Optimizer</span>
        </div>

        <Card className="border-0 shadow-lg">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">{signupCopy.title}</CardTitle>
            <CardDescription className="text-sm sm:text-base">
              {signupCopy.subtitle}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="fullName">{signupCopy.nameLabel}</Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    id="fullName"
                    type="text"
                    placeholder={signupCopy.namePlaceholder}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="h-12 pl-10"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">{signupCopy.emailLabel}</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    id="email"
                    type="email"
                    placeholder={signupCopy.emailPlaceholder}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-12 pl-10"
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">{signupCopy.passwordLabel}</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    id="password"
                    type="password"
                    placeholder={signupCopy.passwordPlaceholder}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-12 pl-10"
                    required
                    minLength={8}
                  />
                </div>
              </div>
              <Button
                type="submit"
                className="w-full h-12 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {signupCopy.loading}
                  </>
                ) : (
                  signupCopy.button
                )}
              </Button>
            </form>

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">{signupCopy.divider}</span>
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              className="w-full h-12"
              onClick={() => window.location.href = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/oauth/google`}
            >
              <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              {signupCopy.google}
            </Button>

            <p className="text-xs text-gray-500 text-center mt-4">
              {signupCopy.terms}{' '}
              <Link href="/terms" className="text-violet-600 hover:underline">{signupCopy.termsLink}</Link>
              {' '}and{' '}
              <Link href="/privacy" className="text-violet-600 hover:underline">{signupCopy.privacyLink}</Link>
            </p>

            <div className="mt-6 text-center text-sm text-gray-500">
              {signupCopy.loginPrompt}{' '}
              <Link href="/login" className="text-violet-600 hover:underline font-medium">
                {signupCopy.loginLink}
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-violet-600" />
      </div>
    }>
      <SignupInner />
    </Suspense>
  );
}
