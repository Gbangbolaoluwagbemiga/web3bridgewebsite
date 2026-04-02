"use client";

import React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ClipboardCheck, Clock, Smartphone, MoveRight, Calendar } from "lucide-react";
import { toast } from "sonner";

interface SolidityAssessmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  assessmentUrl: string;
}

export default function SolidityAssessmentModal({
  isOpen,
  onClose,
  assessmentUrl,
}: SolidityAssessmentModalProps) {
  const handleStartNow = () => {
    toast.success("Redirecting to your assessment...");
    window.location.href = assessmentUrl;
  };

  const handleReschedule = () => {
    // Placeholder for reschedule logic
    toast.info("Your request to reschedule has been noted. We'll follow up with you shortly via email.");
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-xl p-0 overflow-hidden rounded-2xl border-none shadow-2xl">
        <div className="bg-gradient-to-br from-bridgeRed via-red-600 to-red-800 p-8 text-white">
          <div className="w-16 h-16 bg-white/20 backdrop-blur-md rounded-2xl flex items-center justify-center mb-6 border border-white/30 rotate-3">
            <ClipboardCheck className="w-8 h-8 text-white" />
          </div>
          <DialogHeader className="text-left space-y-2 p-0">
            <DialogTitle className="text-3xl font-black tracking-tight leading-tight">
              Ready for Your <br /> Assessment?
            </DialogTitle>
            <DialogDescription className="text-red-100 text-base leading-relaxed opacity-90">
              Congratulations on completing your registration! Before you proceed, there's one final step to secure your spot.
            </DialogDescription>
          </DialogHeader>
        </div>

        <div className="p-8 space-y-8 bg-white dark:bg-zinc-950">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-gray-50 dark:bg-zinc-900 border border-gray-100 dark:border-zinc-800 flex items-start gap-3 transition-colors hover:bg-gray-100 dark:hover:bg-zinc-800/80">
              <div className="mt-1 p-2 bg-red-100 dark:bg-red-900/40 rounded-lg">
                <Clock className="w-4 h-4 text-bridgeRed" />
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Format</p>
                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">20 Random Questions</p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-gray-50 dark:bg-zinc-900 border border-gray-100 dark:border-zinc-800 flex items-start gap-3 transition-colors hover:bg-gray-100 dark:hover:bg-zinc-800/80">
              <div className="mt-1 p-2 bg-blue-100 dark:bg-blue-900/40 rounded-lg">
                <Smartphone className="w-4 h-4 text-blue-600" />
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Device</p>
                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">Mobile & Web Friendly</p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-start gap-4">
              <div className="w-6 h-6 rounded-full bg-red-50 dark:bg-red-900/20 flex items-center justify-center shrink-0 border border-red-100 dark:border-red-800 mt-1">
                <div className="w-2 h-2 rounded-full bg-bridgeRed animate-pulse" />
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed font-medium">
                The assessment is based on your preferred programming language and evaluates your foundational technical skills.
              </p>
            </div>
            
            <div className="flex items-start gap-4">
              <div className="w-6 h-6 rounded-full bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center shrink-0 border border-blue-100 dark:border-blue-800 mt-1">
                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed font-medium">
                You can choose to start now or reschedule for a later time if you're not ready.
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-4">
            <Button
              variant="outline"
              onClick={handleReschedule}
              className="flex-1 h-14 rounded-full border-2 font-bold text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-all active:scale-95 group"
            >
              <Calendar className="w-5 h-5 mr-2 transition-transform group-hover:scale-110" /> Reschedule Later
            </Button>
            <Button
              onClick={handleStartNow}
              className="flex-[1.5] h-14 bg-bridgeRed hover:bg-bridgeRed/90 text-white rounded-full font-bold shadow-lg shadow-red-500/20 transition-all hover:scale-[1.02] active:scale-[0.98] group"
            >
              Start Assessment Now <MoveRight className="w-5 h-5 ml-2 transition-transform group-hover:translate-x-1" />
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
