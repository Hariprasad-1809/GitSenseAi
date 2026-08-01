import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as zod from 'zod';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { emailService } from '../../services/emailjs';
import { ContactFormData } from '../../types';
import { toast } from 'sonner';

interface ContactModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const contactSchema = zod.object({
  name: zod.string().min(2, 'Name must be at least 2 characters.'),
  email: zod.string().email('Please enter a valid email address.'),
  message: zod.string().min(10, 'Message must be at least 10 characters.'),
});

export function ContactModal({ isOpen, onClose }: ContactModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ContactFormData>({
    resolver: zodResolver(contactSchema),
    defaultValues: {
      name: '',
      email: '',
      message: '',
    },
  });

  const onSubmit = async (data: ContactFormData) => {
    setIsSubmitting(true);
    try {
      await emailService.sendContactMessage(data);
      toast.success('Message sent.');
      reset();
      onClose();
    } catch (err) {
      console.error('Failed to submit message:', err);
      toast.error('Failed to send. Try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Contact & Feedback">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <p className="text-[#6b6b6b] text-[11px] leading-relaxed mb-4">
          Need support, found an issue, or want to suggest new features? Send a request parameters map below.
        </p>

        {/* Name input */}
        <div className="space-y-1">
          <label htmlFor="name" className="block text-[10px] font-bold text-[#d4af37] uppercase tracking-wider">
            // your_name
          </label>
          <input
            id="name"
            type="text"
            {...register('name')}
            className="w-full bg-[#0a0a0a] border border-[#2b2b2b] px-3.5 py-2 text-[#ffffff] text-xs focus:outline-none focus:border-[#d4af37] transition-colors font-mono"
            placeholder="Jane Doe"
          />
          {errors.name && (
            <p className="text-[#e5484d] text-[10px] font-bold mt-1 font-mono uppercase">[ERROR: {errors.name.message}]</p>
          )}
        </div>

        {/* Email input */}
        <div className="space-y-1">
          <label htmlFor="email" className="block text-[10px] font-bold text-[#d4af37] uppercase tracking-wider">
            // email_address
          </label>
          <input
            id="email"
            type="email"
            {...register('email')}
            className="w-full bg-[#0a0a0a] border border-[#2b2b2b] px-3.5 py-2 text-[#ffffff] text-xs focus:outline-none focus:border-[#d4af37] transition-colors font-mono"
            placeholder="jane@company.com"
          />
          {errors.email && (
            <p className="text-[#e5484d] text-[10px] font-bold mt-1 font-mono uppercase">[ERROR: {errors.email.message}]</p>
          )}
        </div>

        {/* Message Input */}
        <div className="space-y-1">
          <label htmlFor="message" className="block text-[10px] font-bold text-[#d4af37] uppercase tracking-wider">
            // message_body
          </label>
          <textarea
            id="message"
            rows={4}
            {...register('message')}
            className="w-full bg-[#0a0a0a] border border-[#2b2b2b] px-3.5 py-2 text-[#ffffff] text-xs focus:outline-none focus:border-[#d4af37] transition-colors resize-none font-mono"
            placeholder="Describe your request in detail..."
          />
          {errors.message && (
            <p className="text-[#e5484d] text-[10px] font-bold mt-1 font-mono uppercase">[ERROR: {errors.message.message}]</p>
          )}
        </div>

        {/* Actions panel */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#2b2b2b] mt-6">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit">
            Send Message
          </Button>
        </div>
      </form>
    </Modal>
  );
}
