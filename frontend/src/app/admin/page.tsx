"use client";

import Link from "next/link";
import { BookOpen, ClipboardList, BarChart3 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const CARDS = [
  {
    href: "/admin/contents",
    icon: BookOpen,
    title: "Courses",
    description: "Register AI-generated courses and edit their metadata.",
  },
  {
    href: "/admin/campaigns",
    icon: ClipboardList,
    title: "Campaigns",
    description: "Open evaluation campaigns and assign courses to evaluators.",
  },
  {
    href: "/admin/reports",
    icon: BarChart3,
    title: "Reports",
    description: "Scores, inter-rater agreement and per-evaluator progress.",
  },
];

export default function AdminHome() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-semibold tracking-tight">Admin console</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Register courses → open a campaign → assign evaluators → read the results.
      </p>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {CARDS.map((card) => (
          <Link key={card.href} href={card.href}>
            <Card className="h-full transition-colors hover:border-primary/40 hover:bg-accent/40">
              <CardHeader>
                <card.icon className="h-5 w-5 text-primary" />
                <CardTitle className="mt-2">{card.title}</CardTitle>
                <CardDescription>{card.description}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
