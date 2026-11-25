import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EvidenceLadder } from "@/components/explain/evidence-ladder";
import { OutcomesCalculator } from "@/components/explain/outcomes-calculator";

/**
 * What a newcomer needs before reading a result, in the order they need it: what is
 * checked, how a check is decided, what its outcome means, and why nothing is added up.
 *
 * It explains the model; it holds no data, so it renders without a request. The copy uses
 * the GLOSSARY's words (ADR-0069) and links to the pages where each thing lives.
 */
const MECHANISMS: { name: string; model: string; code: string }[] = [
  {
    name: "Code decides",
    model: "Nothing.",
    code: "Counts, checks presence and order, computes measures such as lexical load, and applies the pass condition.",
  },
  {
    name: "A model reads, code decides",
    model: "Reads the course and returns data, each item tied to a quote: which task measures which objective, where each concept appears.",
    code: "Checks every quote against the text and applies the pass condition to the data: a count, an order, a trajectory.",
  },
  {
    name: "A model judges",
    model: "Answers the pass condition itself, citing a passage. Used where no mechanical check exists.",
    code: "Checks the citation, asks twice, a third time only if the two answers disagree, and takes the majority.",
  },
  {
    name: "Nobody decides",
    model: "—",
    code: "The assessor declares it does not check this criterion. It ends not assessed: a gap in coverage, not a fail.",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">How evaluation works</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Four short sections. Read them once before your first study, and come back when a
          result surprises you.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>1 · What is checked</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            An <Link href="/admin/instruments" className="text-primary hover:underline">instrument</Link>{" "}
            lists claims about a course and the criteria that check each claim. Every result
            climbs down this ladder to a passage of the course. Pick a step.
          </p>
          <EvidenceLadder />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2 · Who decides a criterion</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            The instrument says what is checked. An{" "}
            <Link href="/admin/assessors" className="text-primary hover:underline">assessor</Link>{" "}
            decides how, criterion by criterion, in one of four ways. A model never has the
            last word on its own, and a different algorithm, prompt or model is a different
            assessor.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-sm">
              <thead>
                <tr className="border-b text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">How</th>
                  <th className="py-2 pr-3 font-medium">What a model does</th>
                  <th className="py-2 font-medium">What code does</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {MECHANISMS.map((mechanism) => (
                  <tr key={mechanism.name} className="align-top">
                    <td className="py-2 pr-3 font-medium">{mechanism.name}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{mechanism.model}</td>
                    <td className="py-2 text-muted-foreground">{mechanism.code}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted-foreground">
            The Assessors page says how many criteria each assessor decides, and whether it
            spends model calls to do it.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3 · What an outcome means</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Every criterion of every course ends in one of six states. Change them below and
            watch the two places they are counted.
          </p>
          <OutcomesCalculator />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>4 · Why there is no overall score</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            A course is never reduced to one number. Adding five dimensions into one takes
            weights, and the weights are a judgment about what matters: with different
            weights, two generator versions can swap places. That judgment is not the
            instrument&apos;s to make.
          </p>
          <p>
            So results are read claim by claim and criterion by criterion. Where a number is
            computed, it covers one declared set and travels with its coverage. If your work
            needs a single number, choose the weights yourself and write them down.
          </p>
        </CardContent>
      </Card>

      <p className="text-sm text-muted-foreground">
        Experts are the other half: in a{" "}
        <Link href="/admin/campaigns" className="text-primary hover:underline">campaign</Link>,
        they rate courses one quality at a time, and their ratings are what each claim is
        checked against.
      </p>
    </div>
  );
}
