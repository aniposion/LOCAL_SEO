'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Loader2, Lock, Mail, MapPin } from 'lucide-react';
import { toast } from 'sonner';

import { authApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const loginCopy = {
  title: 'Welcome back',
  subtitle: 'Pick up where you left off. Check approvals, reviews, and performance in seconds.',
  emailLabel: 'Email',
  emailPlaceholder: 'you@example.com',
  passwordLabel: 'Password',
  passwordPlaceholder: 'Enter your password',
  forgotPassword: 'Forgot password?',
  button: 'Sign in',
  loading: 'Signing you in...',
  divider: 'Or sign in with',
  google: 'Continue with Google',
  signupPrompt: 'New here?',
  signupLink: 'Start your free preview',
  error: 'Please enter your email and password.',
};

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error(loginCopy.error);
      return;
    }

    setIsLoading(true);
    try {
      const response = await authApi.login(email, password);
      const { access_token, user } = response.data;
      login(access_token, user);
      toast.success('Welcome back. Opening your dashboard.');
      router.push('/dashboard');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Invalid email or password'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="w-10 h-10 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center">
            <MapPin className="w-6 h-6 text-white" />
          </div>
          <span className="font-bold text-2xl">Local SEO Optimizer</span>
        </div>

        <Card className="border-0 shadow-lg">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">{loginCopy.title}</CardTitle>
            <CardDescription className="text-sm sm:text-base">
              {loginCopy.subtitle}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">{loginCopy.emailLabel}</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    id="email"
                    type="email"
                    placeholder={loginCopy.emailPlaceholder}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-12 pl-10"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">{loginCopy.passwordLabel}</Label>
                  <Link href="/forgot-password" className="text-sm text-violet-600 hover:underline">
                    {loginCopy.forgotPassword}
                  </Link>
                </div>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    id="password"
                    type="password"
                    placeholder={loginCopy.passwordPlaceholder}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-12 pl-10"
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
                    {loginCopy.loading}
                  </>
                ) : (
                  loginCopy.button
                )}
              </Button>
            </form>

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">{loginCopy.divider}</span>
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              className="w-full h-12"
              onClick={() => {
                window.location.href = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/oauth/google`;
              }}
            >
              <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              {loginCopy.google}
            </Button>

            <div className="mt-6 text-center text-sm text-gray-500">
              {loginCopy.signupPrompt}{' '}
              <Link href="/signup" className="text-violet-600 hover:underline font-medium">
                {loginCopy.signupLink}
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
