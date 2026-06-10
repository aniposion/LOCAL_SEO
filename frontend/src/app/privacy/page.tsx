'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { privacyCopy } from '@/lib/copy';

export default function PrivacyPage() {
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
          <h1 className="text-3xl font-bold">{privacyCopy.title}</h1>
          <p className="text-gray-600 mt-2">{privacyCopy.lastUpdated}</p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="bg-white rounded-xl shadow-sm p-8 space-y-8">
          <p className="text-gray-600 bg-green-50 p-4 rounded-lg border border-green-100">
            {privacyCopy.intro}
          </p>
          <section>
            <h2 className="text-xl font-semibold mb-4">1. Information We Collect</h2>
            <p className="text-gray-600 mb-4">
              We collect information you provide directly to us, such as when you create an account,
              use our services, or contact us for support.
            </p>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>Account information (name, email, password)</li>
              <li>Business information (business name, address, phone number)</li>
              <li>Content you create or upload (posts, images, reviews)</li>
              <li>Usage data and analytics</li>
              <li>Communication preferences</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">2. How We Use Your Information</h2>
            <p className="text-gray-600 mb-4">We use the information we collect to:</p>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>Provide, maintain, and improve our services</li>
              <li>Process transactions and send related information</li>
              <li>Send technical notices, updates, and support messages</li>
              <li>Respond to your comments, questions, and requests</li>
              <li>Monitor and analyze trends, usage, and activities</li>
              <li>Detect, investigate, and prevent fraudulent transactions</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">3. Information Sharing</h2>
            <p className="text-gray-600 mb-4">
              We do not sell, trade, or otherwise transfer your personal information to third parties
              without your consent, except as described in this policy:
            </p>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>With service providers who assist in our operations</li>
              <li>To comply with legal obligations</li>
              <li>To protect our rights and prevent fraud</li>
              <li>With your consent or at your direction</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">4. Data Security</h2>
            <p className="text-gray-600">
              We implement appropriate technical and organizational measures to protect your personal
              information against unauthorized access, alteration, disclosure, or destruction. This
              includes encryption, secure servers, and regular security assessments.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">5. Your Rights</h2>
            <p className="text-gray-600 mb-4">You have the right to:</p>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>Access your personal information</li>
              <li>Correct inaccurate data</li>
              <li>Request deletion of your data</li>
              <li>Object to processing of your data</li>
              <li>Export your data in a portable format</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">6. Cookies</h2>
            <p className="text-gray-600">
              We use cookies and similar tracking technologies to track activity on our service and
              hold certain information. You can instruct your browser to refuse all cookies or to
              indicate when a cookie is being sent.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-4">7. Contact Us</h2>
            <p className="text-gray-600">
              If you have any questions about this Privacy Policy, please contact us at{' '}
              <a href="mailto:privacy@localseo.app" className="text-violet-600 hover:underline">
                privacy@localseo.app
              </a>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
