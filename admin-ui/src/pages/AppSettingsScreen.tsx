import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetFooter, SheetClose } from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Trash, Edit, Plus } from "lucide-react";

interface AppSetting {
  id: string;
  config_name: string;
  query?: string;
  language?: string;
  country?: string;
  enabled?: boolean;
  [key: string]: any;
}

export default function AppSettingsScreen() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Partial<AppSetting>>({});
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [newSetting, setNewSetting] = useState<Partial<AppSetting>>({
    config_name: "", query: "", language: "", country: "", enabled: true
  });

  const { data: settings, isLoading } = useQuery({
    queryKey: ["app-settings"],
    queryFn: async () => {
      const res = await apiClient.get<AppSetting[]>("/app-settings/");
      return res.data;
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: Partial<AppSetting> }) => {
      const res = await apiClient.put(`/app-settings/${id}`, updates);
      return res.data;
    },
    onSuccess: () => {
      toast({ title: "Updated", description: "App Setting saved." });
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["app-settings"] });
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: Partial<AppSetting>) => {
      const res = await apiClient.post(`/app-settings/`, data);
      return res.data;
    },
    onSuccess: () => {
      toast({ title: "Created", description: "New App Setting added." });
      setIsSheetOpen(false);
      setNewSetting({ config_name: "", query: "", language: "", country: "", enabled: true });
      queryClient.invalidateQueries({ queryKey: ["app-settings"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/app-settings/${id}`),
    onSuccess: () => {
      toast({ title: "Deleted", description: "App Setting removed." });
      queryClient.invalidateQueries({ queryKey: ["app-settings"] });
    },
  });

  const handleSave = (id: string) => updateMutation.mutate({ id, updates: editValues });
  const handleToggle = (id: string, val: boolean) => updateMutation.mutate({ id, updates: { enabled: val } });
  
  const handleAddSubmit = () => {
    if (!newSetting.config_name) {
      toast({ title: "Error", description: "Config Name is required", variant: "destructive" });
      return;
    }
    createMutation.mutate(newSetting);
  };

  if (isLoading) return <div className="p-8">Loading Settings...</div>;

  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">App Settings</h2>
          <p className="text-muted-foreground">Manage dynamic configurations like search terms and regions.</p>
          <p className="text-xs text-muted-foreground">
            Collection: <span className="font-mono">app_settings</span> | Key: <span className="font-mono">_id (id)</span>
          </p>
        </div>
        <Button onClick={() => setIsSheetOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> Add Config
        </Button>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Config Name</TableHead>
                  <TableHead>Query</TableHead>
                  <TableHead>Language</TableHead>
                  <TableHead>Country</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[140px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {settings?.map((setting) => {
                  const isEditing = editingId === setting.id;
                  return (
                    <TableRow key={setting.id}>
                      <TableCell className="font-medium">{setting.config_name}</TableCell>
                      <TableCell>
                        {isEditing ? (
                          <Input defaultValue={setting.query || ""} onChange={(e) => setEditValues({ ...editValues, query: e.target.value })} />
                        ) : (setting.query || "-")}
                      </TableCell>
                      <TableCell>
                        {isEditing ? (
                          <Input defaultValue={setting.language || ""} onChange={(e) => setEditValues({ ...editValues, language: e.target.value })} />
                        ) : (setting.language || "-")}
                      </TableCell>
                      <TableCell>
                        {isEditing ? (
                          <Input defaultValue={setting.country || ""} onChange={(e) => setEditValues({ ...editValues, country: e.target.value })} />
                        ) : (setting.country || "-")}
                      </TableCell>
                      <TableCell>
                        <Switch 
                          checked={setting.enabled !== false} 
                          onCheckedChange={(val) => handleToggle(setting.id, val)}
                          disabled={isEditing}
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        {isEditing ? (
                          <div className="flex gap-2 justify-end">
                            <Button size="sm" onClick={() => handleSave(setting.id)}>Save</Button>
                            <Button size="sm" variant="outline" onClick={() => setEditingId(null)}>Cancel</Button>
                          </div>
                        ) : (
                          <div className="flex gap-2 justify-end">
                            <Button variant="ghost" size="icon" onClick={() => {
                              setEditingId(setting.id);
                              setEditValues({});
                            }}>
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="text-destructive" onClick={() => {
                              if (confirm("Delete this setting?")) deleteMutation.mutate(setting.id);
                            }}>
                              <Trash className="h-4 w-4" />
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
                {settings?.length === 0 && (
                  <TableRow><TableCell colSpan={6} className="text-center py-6">No application settings found.</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
        <SheetContent className="w-[400px] sm:w-[540px]">
          <SheetHeader>
            <SheetTitle>Add New App Setting</SheetTitle>
            <SheetDescription>Create a new configuration block for the application.</SheetDescription>
          </SheetHeader>
          <div className="grid gap-4 py-4 mt-4">
            <div className="grid gap-2">
              <Label>Config Name *</Label>
              <Input placeholder="e.g. radio_search_by_place" value={newSetting.config_name} onChange={(e) => setNewSetting({...newSetting, config_name: e.target.value})} />
            </div>
            <div className="grid gap-2">
              <Label>Query</Label>
              <Input value={newSetting.query} onChange={(e) => setNewSetting({...newSetting, query: e.target.value})} />
            </div>
            <div className="grid gap-2">
              <Label>Language</Label>
              <Input value={newSetting.language} onChange={(e) => setNewSetting({...newSetting, language: e.target.value})} />
            </div>
            <div className="grid gap-2">
              <Label>Country</Label>
              <Input value={newSetting.country} onChange={(e) => setNewSetting({...newSetting, country: e.target.value})} />
            </div>
            <div className="flex items-center justify-between mt-2">
              <Label>Enabled</Label>
              <Switch checked={newSetting.enabled} onCheckedChange={(val) => setNewSetting({...newSetting, enabled: val})} />
            </div>
          </div>
          <SheetFooter className="mt-6">
            <SheetClose asChild><Button variant="outline">Cancel</Button></SheetClose>
            <Button onClick={handleAddSubmit} disabled={createMutation.isPending || !newSetting.config_name}>Create</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
