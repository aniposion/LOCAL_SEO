'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { termsCopy } from '@/lib/copy';

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <Link
            href="/"
            className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to Home
          </Link>
          <h1 className="text-3xl font-bold">{termsCopy.title}</h1>
          <p className="text-gray-600 mt-2">{termsCopy.lastUpdated}</p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="bg-white rounded-xl shadow-sm p-8 space-y-8">
          <p className="text-gray-600 bg-violet-50 p-4 rounded-lg border border-violet-100">
            {termsCopy.intro}
          </p>
          <section>
            <h2 className="text-xl font-semibold mb-4">1. Acceptance of Terms</h2>
            <p className="text-gray-600">
              By accessing or using Local SEO Optimizer (&quot;Service&quot;), you agree to be bound by these
              Terms of Service. If you do not agree to these terms, please do not use our Service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">2. Description of Service</h2>
            <p className="text-gray-600">
              Local SEO Optimizer provides tools and services to help businesses manage their local
              online presence, including but not limited to: content creation, social media management,
              review monitoring, and SEO optimization.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">3. Account Registration</h2>
            <p className="text-gray-600 mb-4">To use our Service, you must:</p>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>Be at least 18 years old</li>
              <li>Provide accurate and complete registration information</li>
              <li>Maintain the security of your account credentials</li>
              <li>Notify us immediately of any unauthorized use</li>
              <li>Be responsible for all activities under your account</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">4. Subscription and Payments</h2>
            <p className="text-gray-600 mb-4">
              Some features of our Service require a paid subscription:
            </p>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>Subscription fees are billed in advance on a monthly or annual basis</li>
              <li>All fees are non-refundable except as required by law</li>
              <li>We may change our fees with 30 days notice</li>
              <li>You can cancel your subscription at any time</li>
              <li>Cancellation takes effect at the end of the current billing period</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">5. Acceptable Use</h2>
            <p className="text-gray-600 mb-4">You agree not to:</p>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>Violate any applicable laws or regulations</li>
              <li>Infringe on intellectual property rights</li>
              <li>Transmit harmful, offensive, or illegal content</li>
              <li>Attempt to gain unauthorized access to our systems</li>
              <li>Use the Service for spam or unsolicited communications</li>
              <li>Interfere with or disrupt the Service</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">6. Content Ownership</h2>
            <p className="text-gray-600">
              You retain ownership of content you create using our Service. By using our Service,
              you grant us a license to use, store, and display your content as necessary to
              provide the Service. We do not claim ownership of your content.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">7. AI-Generated Content</h2>
            <p className="text-gray-600">
              Our Service uses artificial intelligence to generate content suggestions. You are
              responsible for reviewing and approving all AI-generated content before publication.
              We do not guarantee the accuracy or appropriateness of AI-generated content.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">8. Limitation of Liability</h2>
            <p className="text-gray-600">
              To the maximum extent permitted by law, Local SEO Optimizer shall not be liable for
              any indirect, incidental, special, consequential, or punitive damages resulting from
              your use of or inability to use the Service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">9. Termination</h2>
            <p className="text-gray-600">
              We may terminate or suspend your account at any time for violations of these Terms.
              Upon termination, your right to use the Service will immediately cease. You may
              request export of your data within 30 days of termination.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">10. Changes to Terms</h2>
            <p className="text-gray-600">
              We reserve the right to modify these Terms at any time. We will notify you of
              significant changes via email or through the Service. Continued use after changes
              constitutes acceptance of the new Terms.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">11. Contact</h2>
            <p className="text-gray-600">
              For questions about these Terms, please contact us at{' '}
              <a href="mailto:legal@localseo.app" className="text-violet-600 hover:underline">
                legal@localseo.app
              </a>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
