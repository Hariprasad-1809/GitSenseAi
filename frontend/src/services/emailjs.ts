import emailjs from '@emailjs/browser';
import { ContactFormData } from '../types';

const SERVICE_ID = import.meta.env.VITE_EMAILJS_SERVICE_ID || '';
const TEMPLATE_ID = import.meta.env.VITE_EMAILJS_TEMPLATE_ID || '';
const PUBLIC_KEY = import.meta.env.VITE_EMAILJS_PUBLIC_KEY || '';

export const emailService = {
  /**
   * Sends the contact form email via EmailJS
   */
  async sendContactMessage(data: ContactFormData): Promise<void> {
    if (!SERVICE_ID || !TEMPLATE_ID || !PUBLIC_KEY) {
      console.warn('EmailJS environment variables are missing. Simulating successful send.');
      return new Promise((resolve) => setTimeout(resolve, 1000));
    }

    const templateParams = {
      from_name: data.name,
      from_email: data.email,
      message: data.message,
    };

    await emailjs.send(SERVICE_ID, TEMPLATE_ID, templateParams, PUBLIC_KEY);
  }
};
