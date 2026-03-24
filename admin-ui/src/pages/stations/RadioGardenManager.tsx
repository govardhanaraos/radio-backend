import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetFooter, SheetClose } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Trash, Edit, Plus, Search } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface DBGardenStation {
  id_mongo: string;
  id?: string;
  radio_garden_id?: string;
  name: string;
  logoUrl?: string;
  streamUrl: string;
  language?: string;
  genre?: string;
  country?: string;
  state?: string;
  page?: string;
}

export default function RadioGardenManager() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [editingStation, setEditingStation] = useState<DBGardenStation | null>(null);
  const [formData, setFormData] = useState<Partial<DBGardenStation>>({});
  const [searchTerm, setSearchTerm] = useState("");

  const { data: stations, isLoading } = useQuery({
    queryKey: ["admin-radio-garden"],
    queryFn: async () => {
      const res = await apiClient.get<DBGardenStation[]>("/admin-stations/radio-garden");
      return res.data;
    },
  });

  const filteredStations = useMemo(() => {
    if (!stations) return [];
    if (!searchTerm) return stations;
    const lower = searchTerm.toLowerCase();
    return stations.filter(s => 
      s.name?.toLowerCase().includes(lower) || 
      s.language?.toLowerCase().includes(lower) || 
      s.genre?.toLowerCase().includes(lower) || 
      s.page?.toLowerCase().includes(lower) ||
      s.state?.toLowerCase().includes(lower) ||
      s.country?.toLowerCase().includes(lower)
    );
  }, [stations, searchTerm]);

  const createMutation = useMutation({
    mutationFn: async (data: Partial<DBGardenStation>) => apiClient.post("/admin-stations/radio-garden", data),
    onSuccess: () => {
      toast({ title: "Created", description: "Garden Station added." });
      setIsSheetOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin-radio-garden"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<DBGardenStation> }) => 
      apiClient.put(`/admin-stations/radio-garden/${id}`, data),
    onSuccess: () => {
      toast({ title: "Updated", description: "Garden Station updated." });
      setIsSheetOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin-radio-garden"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/admin-stations/radio-garden/${id}`),
    onSuccess: () => {
      toast({ title: "Deleted", description: "Station removed." });
      queryClient.invalidateQueries({ queryKey: ["admin-radio-garden"] });
    },
  });

  const handleOpenSheet = (station?: DBGardenStation) => {
    if (station) {
      setEditingStation(station);
      setFormData(station);
    } else {
      setEditingStation(null);
      setFormData({ name: "", radio_garden_id: "", streamUrl: "", logoUrl: "", language: "", genre: "", page: "", country: "", state: "", id: "" });
    }
    setIsSheetOpen(true);
  };

  const handleSave = () => {
    const dataToSave = { ...formData };
    if (!dataToSave.id) dataToSave.id = Math.floor(Math.random() * 100000000).toString();

    if (editingStation) {
      updateMutation.mutate({ id: editingStation.id_mongo, data: dataToSave });
    } else {
      createMutation.mutate(dataToSave);
    }
  };

  const isFormValid = formData.name && formData.streamUrl && formData.logoUrl && formData.language && formData.genre && formData.page && formData.country && formData.state && formData.radio_garden_id;

  return (
    <div className="flex flex-col gap-4 border rounded-lg p-4 bg-background">
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <div>
          <h3 className="text-xl font-semibold">Radio Garden Channels</h3>
          <p className="text-sm text-muted-foreground">Manage entries in the radio_garden_channels collection.</p>
          <p className="text-xs text-muted-foreground">
            Key: <span className="font-mono">_id (id_mongo)</span>
          </p>
        </div>
        <div className="flex items-center gap-4 flex-1 justify-end">
          <div className="relative w-full max-w-xs">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search..."
              className="pl-8"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <Button onClick={() => handleOpenSheet()}>
            <Plus className="mr-2 h-4 w-4" /> Add Garden Channel
          </Button>
        </div>
      </div>

      <div className="rounded-md border max-h-[600px] overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Logo</TableHead>
              <TableHead>Name / Region</TableHead>
              <TableHead>Garden ID / Stream</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={4} className="text-center py-8">Loading...</TableCell></TableRow>
            ) : filteredStations?.length === 0 ? (
               <TableRow><TableCell colSpan={4} className="text-center py-8">No stations found.</TableCell></TableRow>
            ) : (
              filteredStations?.map(station => (
                <TableRow key={station.id_mongo}>
                  <TableCell>
                    {station.logoUrl ? (
                      <img src={station.logoUrl} className="w-8 h-8 rounded object-cover bg-black/10" />
                    ) : <div className="w-8 h-8 bg-muted rounded" />}
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">{station.name}</div>
                    <div className="text-xs text-muted-foreground">{station.state}, {station.country}</div>
                  </TableCell>
                  <TableCell>
                    <div className="text-xs font-mono bg-muted inline-block px-1 rounded">{station.radio_garden_id || "None"}</div>
                    <div className="max-w-[200px] truncate text-xs mt-1">{station.streamUrl}</div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" onClick={() => handleOpenSheet(station)}>
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="text-destructive" onClick={() => {
                        if (confirm('Are you sure you want to delete this radio garden station?')) {
                          deleteMutation.mutate(station.id_mongo);
                        }
                      }}>
                      <Trash className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
        <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{editingStation ? "Edit Radio Garden Channel" : "Add Garden Channel"}</SheetTitle>
            <SheetDescription>Make changes to the radio garden database record here. All fields are required except ID.</SheetDescription>
          </SheetHeader>
          <div className="grid gap-4 py-4">
            {["name", "radio_garden_id", "streamUrl", "logoUrl", "language", "genre", "country", "state", "page", "id"].map((field) => (
              <div key={field} className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor={field} className="text-right capitalize">
                  {field.replace(/_/g, " ")}{field !== "id" && " *"}
                </Label>
                <Input
                  id={field}
                  value={formData[field as keyof DBGardenStation] || ""}
                  onChange={(e) => setFormData({ ...formData, [field]: e.target.value })}
                  placeholder={field === "id" ? "(Auto Generated)" : ""}
                  className="col-span-3"
                />
              </div>
            ))}
          </div>
          <SheetFooter>
            <SheetClose asChild>
              <Button variant="outline">Cancel</Button>
            </SheetClose>
            <Button onClick={handleSave} disabled={createMutation.isPending || updateMutation.isPending || !isFormValid}>
              Save changes
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
