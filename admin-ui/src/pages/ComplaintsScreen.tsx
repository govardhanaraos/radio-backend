import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { MessageSquare } from "lucide-react";

export interface ComplaintRow {
  _id: string;
  reference_no: string;
  name: string;
  subject: string;
  email: string;
  contact?: string;
  description: string;
  device_id?: string;
  status?: string;
  created_at?: string;
  admin_response?: string;
  replied_at?: string;
}

export default function ComplaintsScreen() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<ComplaintRow | null>(null);
  const [replyDraft, setReplyDraft] = useState("");

  const { data: rows, isLoading } = useQuery({
    queryKey: ["admin-complaints"],
    queryFn: async () => {
      const res = await apiClient.get<ComplaintRow[]>("/admin/complaints");
      return res.data;
    },
  });

  const openSheet = (row: ComplaintRow) => {
    setSelected(row);
    setReplyDraft(row.admin_response ?? "");
  };

  const replyMutation = useMutation({
    mutationFn: async ({ id, text }: { id: string; text: string }) => {
      const res = await apiClient.patch<ComplaintRow>(`/admin/complaints/${id}`, {
        admin_response: text,
      });
      return res.data;
    },
    onSuccess: () => {
      toast({ title: "Saved", description: "Your reply was saved. Users can load it via reference number." });
      queryClient.invalidateQueries({ queryKey: ["admin-complaints"] });
      setSelected(null);
      setReplyDraft("");
    },
    onError: (err: Error) => {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    },
  });

  const handleSaveReply = () => {
    if (!selected) return;
    const text = replyDraft.trim();
    if (!text) {
      toast({ title: "Reply required", description: "Enter a message before saving.", variant: "destructive" });
      return;
    }
    replyMutation.mutate({ id: selected._id, text });
  };

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Loading complaints…</div>;
  }

  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto">
      <div>
        <h2 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <MessageSquare className="h-8 w-8" />
          Customer feedback
        </h2>
        <p className="text-muted-foreground">
          View complaints from the mobile app and send a reply. Users see the response when they check by
          reference number.
        </p>
        <p className="text-xs text-muted-foreground">
          Collection: <span className="font-mono">cust_feedback_complaints</span> | Key:{" "}
          <span className="font-mono">_id</span>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Complaints</CardTitle>
          <CardDescription>
            Status <span className="font-mono">P</span> = pending, <span className="font-mono">R</span> = replied
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0 sm:p-6">
          <ScrollArea className="h-[min(70vh,640px)] rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ref</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Device</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead className="text-right w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows?.map((row) => (
                  <TableRow key={row._id}>
                    <TableCell className="font-mono text-xs">{row.reference_no}</TableCell>
                    <TableCell className="max-w-[200px] truncate">{row.subject}</TableCell>
                    <TableCell>{row.name}</TableCell>
                    <TableCell className="font-mono text-xs max-w-[120px] truncate">
                      {row.device_id ?? "—"}
                    </TableCell>
                    <TableCell>
                      <span
                        className={cn(
                          "rounded px-2 py-0.5 text-xs font-medium",
                          row.status === "R"
                            ? "bg-green-500/15 text-green-700 dark:text-green-400"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {row.status ?? "P"}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                      {row.created_at
                        ? new Date(row.created_at).toLocaleString()
                        : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" onClick={() => openSheet(row)}>
                        View / reply
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {rows?.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-10 text-muted-foreground">
                      No complaints yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      <Sheet open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent className="w-full sm:max-w-lg flex flex-col gap-0">
          <SheetHeader>
            <SheetTitle>{selected?.subject}</SheetTitle>
            <SheetDescription className="font-mono text-xs">
              {selected?.reference_no}
            </SheetDescription>
          </SheetHeader>
          {selected && (
            <ScrollArea className="flex-1 -mx-6 px-6 min-h-0">
              <div className="space-y-4 pb-4 text-sm">
                <div>
                  <p className="text-muted-foreground text-xs">Name</p>
                  <p>{selected.name}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Email</p>
                  <p>{selected.email}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Contact</p>
                  <p>{selected.contact ?? "—"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Device ID</p>
                  <p className="font-mono break-all">{selected.device_id ?? "—"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Description</p>
                  <p className="whitespace-pre-wrap rounded-md border bg-muted/30 p-3">{selected.description}</p>
                </div>
                {selected.replied_at && (
                  <div>
                    <p className="text-muted-foreground text-xs">Last reply at</p>
                    <p>{new Date(selected.replied_at).toLocaleString()}</p>
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="admin-reply">Reply to user (shown in app)</Label>
                  <textarea
                    id="admin-reply"
                    className={cn(
                      "flex min-h-[140px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
                      "ring-offset-background placeholder:text-muted-foreground",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                      "disabled:cursor-not-allowed disabled:opacity-50"
                    )}
                    value={replyDraft}
                    onChange={(e) => setReplyDraft(e.target.value)}
                    placeholder="Type your response…"
                  />
                </div>
              </div>
            </ScrollArea>
          )}
          <SheetFooter className="gap-2 sm:justify-end mt-auto pt-4 border-t">
            <Button variant="outline" type="button" onClick={() => setSelected(null)}>
              Close
            </Button>
            <Button type="button" onClick={handleSaveReply} disabled={replyMutation.isPending}>
              {replyMutation.isPending ? "Saving…" : "Save reply"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
