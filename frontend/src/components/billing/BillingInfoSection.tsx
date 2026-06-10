'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, Building2, Save } from 'lucide-react';
import { billingApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';

interface BillingInfo {
  company_name: string;
  tax_id: string;
  tax_id_type: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  billing_email: string;
}

const COUNTRIES = [
  { code: 'US', name: 'United States', taxIdLabel: 'EIN', taxIdType: 'us_ein' },
  { code: 'KR', name: 'South Korea', taxIdLabel: 'Business Registration Number', taxIdType: 'kr_brn' },
  { code: 'GB', name: 'United Kingdom', taxIdLabel: 'VAT Number', taxIdType: 'gb_vat' },
  { code: 'DE', name: 'Germany', taxIdLabel: 'USt-IdNr', taxIdType: 'eu_vat' },
  { code: 'FR', name: 'France', taxIdLabel: 'Num챕ro TVA', taxIdType: 'eu_vat' },
  { code: 'JP', name: 'Japan', taxIdLabel: '力뺜볶?ゅ뤇', taxIdType: 'jp_cn' },
  { code: 'CA', name: 'Canada', taxIdLabel: 'BN', taxIdType: 'ca_bn' },
  { code: 'AU', name: 'Australia', taxIdLabel: 'ABN', taxIdType: 'au_abn' },
];

export function BillingInfoSection() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [billingInfo, setBillingInfo] = useState<BillingInfo>({
    company_name: '',
    tax_id: '',
    tax_id_type: '',
    address_line1: '',
    address_line2: '',
    city: '',
    state: '',
    postal_code: '',
    country: 'US',
    billing_email: '',
  });

  useEffect(() => {
    fetchBillingInfo();
  }, []);

  const fetchBillingInfo = async () => {
    setLoading(true);
    try {
      const response = await billingApi.getBillingInfo();
      if (response.data) {
        setBillingInfo({
          company_name: response.data.company_name || '',
          tax_id: response.data.tax_id || '',
          tax_id_type: response.data.tax_id_type || '',
          address_line1: response.data.address_line1 || '',
          address_line2: response.data.address_line2 || '',
          city: response.data.city || '',
          state: response.data.state || '',
          postal_code: response.data.postal_code || '',
          country: response.data.country || 'US',
          billing_email: response.data.billing_email || '',
        });
      }
    } catch {
      // Use defaults
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await billingApi.updateBillingInfo({
        company_name: billingInfo.company_name,
        tax_id: billingInfo.tax_id,
        tax_id_type: billingInfo.tax_id_type,
        address: {
          line1: billingInfo.address_line1,
          line2: billingInfo.address_line2,
          city: billingInfo.city,
          state: billingInfo.state,
          postal_code: billingInfo.postal_code,
          country: billingInfo.country,
        },
        billing_email: billingInfo.billing_email,
      });
      toast.success('Billing information saved');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to save billing information'));
    } finally {
      setSaving(false);
    }
  };

  const handleCountryChange = (country: string) => {
    const countryData = COUNTRIES.find(c => c.code === country);
    setBillingInfo({
      ...billingInfo,
      country,
      tax_id_type: countryData?.taxIdType || '',
    });
  };

  const selectedCountry = COUNTRIES.find(c => c.code === billingInfo.country);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Company Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="company_name">Company name</Label>
          <div className="relative">
            <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              id="company_name"
              className="pl-10"
              placeholder="Enter company name"
              value={billingInfo.company_name}
              onChange={(e) => setBillingInfo({ ...billingInfo, company_name: e.target.value })}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="billing_email">Billing email</Label>
          <Input
            id="billing_email"
            type="email"
            placeholder="billing@company.com"
            value={billingInfo.billing_email}
            onChange={(e) => setBillingInfo({ ...billingInfo, billing_email: e.target.value })}
          />
        </div>
      </div>

      {/* Tax Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="country">Country</Label>
          <Select value={billingInfo.country} onValueChange={handleCountryChange}>
            <SelectTrigger>
              <SelectValue placeholder="Select country" />
            </SelectTrigger>
            <SelectContent>
              {COUNTRIES.map((country) => (
                <SelectItem key={country.code} value={country.code}>
                  {country.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="tax_id">
            {selectedCountry?.taxIdLabel || 'Tax ID'} (optional)
          </Label>
          <Input
            id="tax_id"
            placeholder={selectedCountry?.taxIdLabel || 'Tax ID'}
            value={billingInfo.tax_id}
            onChange={(e) => setBillingInfo({ ...billingInfo, tax_id: e.target.value })}
          />
        </div>
      </div>

      {/* Address */}
      <div className="space-y-4">
        <Label className="text-sm font-medium">Billing address</Label>

        <div className="space-y-3">
          <Input
            placeholder="Address line 1"
            value={billingInfo.address_line1}
            onChange={(e) => setBillingInfo({ ...billingInfo, address_line1: e.target.value })}
          />

          <Input
            placeholder="Address line 2 (optional)"
            value={billingInfo.address_line2}
            onChange={(e) => setBillingInfo({ ...billingInfo, address_line2: e.target.value })}
          />

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Input
              placeholder="City"
              value={billingInfo.city}
              onChange={(e) => setBillingInfo({ ...billingInfo, city: e.target.value })}
            />
            <Input
              placeholder="State / Province"
              value={billingInfo.state}
              onChange={(e) => setBillingInfo({ ...billingInfo, state: e.target.value })}
            />
            <Input
              placeholder="Postal code"
              value={billingInfo.postal_code}
              onChange={(e) => setBillingInfo({ ...billingInfo, postal_code: e.target.value })}
            />
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-4 border-t">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Save className="w-4 h-4 mr-2" />
          )}
          Save
        </Button>
      </div>
    </div>
  );
}
