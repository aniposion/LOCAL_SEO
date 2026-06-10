'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Mail, ArrowLeft, Loader2, CheckCircle } from 'lucide-react';
import { forgotPasswordCopy } from '@/lib/copy';
import { authApi } from '@/lib/api';
import { toast } from 'sonner';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim()) {
      toast.error(forgotPasswordCopy.hint);
      return;
    }

    setIsLoading(true);
    try {
      await authApi.forgotPassword(email);
      setIsSubmitted(true);
    } catch {
      // Always show success to prevent email enumeration
      setIsSubmitted(true);
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 via-white to-indigo-50 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <Card className="border-0 shadow-xl">
            <CardContent className="pt-8 text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-8 h-8 text-green-600" />
              </div>
              <h2 className="text-xl font-bold mb-2">{forgotPasswordCopy.successTitle}</h2>
              <p className="text-gray-600 mb-6">
                {forgotPasswordCopy.successBody.replace('{email}', email)}
              </p>
              <div className="space-y-3">
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setIsSubmitted(false)}
                >
                  {forgotPasswordCopy.tryAnother}
                </Button>
                <Link href="/login">
                  <Button className="w-full bg-gradient-to-r from-violet-600 to-indigo-600">
                    {forgotPasswordCopy.backToLogin}
                  </Button>
                </Link>
              </div>
              <p className="text-sm text-gray-500 mt-6">
                {forgotPasswordCopy.hint}
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-violet-50 via-white to-indigo-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Back Link */}
        <Link
          href="/login"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          {forgotPasswordCopy.backLink}
        </Link>

        <Card className="border-0 shadow-xl">
          <CardHeader className="text-center pb-2">
            <CardTitle className="text-2xl">{forgotPasswordCopy.title}</CardTitle>
            <CardDescription>
              {forgotPasswordCopy.subtitle}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">{forgotPasswordCopy.emailLabel}</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    id="email"
                    type="email"
                    placeholder={forgotPasswordCopy.emailPlaceholder}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-12 pl-10"
                    required
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
                    {forgotPasswordCopy.loading}
                  </>
                ) : (
                  forgotPasswordCopy.button
                )}
              </Button>
            </form>

            <div className="mt-6 text-center text-sm text-gray-500">
              {forgotPasswordCopy.loginPrompt}{' '}
              <Link href="/login" className="text-violet-600 hover:underline font-medium">
                {forgotPasswordCopy.loginLink}
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
