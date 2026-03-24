import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Trash } from "lucide-react";

interface PremiumUser {
  id: string;
  plain_key: string;
  license_key: string;
  active_devices: string[];
  created_at?: string;
}

export default function PremiumUsersScreen() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: users, isLoading } = useQuery({
    queryKey: ["premium-users-admin"],
    queryFn: async () => {
      const res = await apiClient.get<PremiumUser[]>("/premium-users-admin/");
      return res.data;
    },
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post("/premium-users-admin/", {
        plain_key: Math.random().toString(36).substring(2, 8).toUpperCase(),
        license_key: btoa(Math.random().toString(36)),
        active_devices: [],
        created_at: new Date().toISOString(),
      });
      return res.data;
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Generated new premium key." });
      queryClient.invalidateQueries({ queryKey: ["premium-users-admin"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/premium-users-admin/${id}`);
    },
    onSuccess: () => {
      toast({ title: "Deleted", description: "Premium key revoked." });
      queryClient.invalidateQueries({ queryKey: ["premium-users-admin"] });
    },
  });

  if (isLoading) return <div className="p-8">Loading Premium Users...</div>;

  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Premium Licenses</h2>
          <p className="text-muted-foreground">Manage VIP access keys and linked devices.</p>
          <p className="text-xs text-muted-foreground">
            Collection: <span className="font-mono">premium_users</span> | Key: <span className="font-mono">_id (id)</span>
          </p>
        </div>
        <Button onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
          Generate New Key
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Active Subscriptions</CardTitle>
          <CardDescription>All issued license keys.</CardDescription>
          <p className="text-xs text-muted-foreground">
            Collection: <span className="font-mono">premium_users</span> | Key: <span className="font-mono">_id (id)</span>
          </p>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Plain Key</TableHead>
                  <TableHead>License Hash</TableHead>
                  <TableHead>Devices Linked</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users?.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium tracking-widest">{user.plain_key}</TableCell>
                    <TableCell className="text-muted-foreground text-xs truncate max-w-[200px]">
                      {user.license_key}
                    </TableCell>
                    <TableCell>{user.active_devices?.length || 0} / 3</TableCell>
                    <TableCell>{user.created_at ? new Date(user.created_at).toLocaleDateString() : "-"}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive"
                        onClick={() => {
                          if (confirm("Are you sure you want to revoke this premium license? This action cannot be undone.")) {
                            deleteMutation.mutate(user.id);
                          }
                        }}
                      >
                        <Trash className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {users?.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-6 text-muted-foreground">No premium users issued.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
