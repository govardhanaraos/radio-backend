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

interface DBStation {
  id_mongo: string;
  id?: string;
  name: string;
  logoUrl?: string;
  streamUrl: string;
  language?: string;
  genre?: string;
  page?: string;
}

export default function RadioStationsManager() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [editingStation, setEditingStation] = useState<DBStation | null>(null);
  const [formData, setFormData] = useState<Partial<DBStation>>({});
  const [searchTerm, setSearchTerm] = useState("");

  const { data: stations, isLoading } = useQuery({
    queryKey: ["admin-radio-stations"],
    queryFn: async () => {
      const res = await apiClient.get<DBStation[]>("/admin-stations/radio-stations");
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
      s.page?.toLowerCase().includes(lower)
    );
  }, [stations, searchTerm]);

  const createMutation = useMutation({
    mutationFn: async (data: Partial<DBStation>) => apiClient.post("/admin-stations/radio-stations", data),
    onSuccess: () => {
      toast({ title: "Created", description: "Station added successfully." });
      setIsSheetOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin-radio-stations"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<DBStation> }) => 
      apiClient.put(`/admin-stations/radio-stations/${id}`, data),
    onSuccess: () => {
      toast({ title: "Updated", description: "Station updated successfully." });
      setIsSheetOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin-radio-stations"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/admin-stations/radio-stations/${id}`),
    onSuccess: () => {
      toast({ title: "Deleted", description: "Station removed." });
      queryClient.invalidateQueries({ queryKey: ["admin-radio-stations"] });
    },
  });

  const handleOpenSheet = (station?: DBStation) => {
    if (station) {
      setEditingStation(station);
      setFormData(station);
    } else {
      setEditingStation(null);
      setFormData({ name: "", streamUrl: "", logoUrl: "", language: "", genre: "", page: "", id: "" });
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

  const isFormValid = formData.name && formData.streamUrl && formData.logoUrl && formData.language && formData.genre && formData.page;

  return (
    <div className="flex flex-col gap-4 border rounded-lg p-4 bg-background">
      <div className="flex justify-between items-center mb-4 flex-wrap gap-4">
        <div>
          <h3 className="text-xl font-semibold">Native Radio Stations</h3>
          <p className="text-sm text-muted-foreground">Manage entries in the radio_stations collection.</p>
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
            <Plus className="mr-2 h-4 w-4" /> Add Station
          </Button>
        </div>
      </div>

      <div className="rounded-md border max-h-[600px] overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Logo</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Stream URL</TableHead>
              <TableHead>Language/Genre</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={5} className="text-center py-8">Loading...</TableCell></TableRow>
            ) : filteredStations?.length === 0 ? (
               <TableRow><TableCell colSpan={5} className="text-center py-8">No stations found.</TableCell></TableRow>
            ) : (
              filteredStations?.map(station => (
                <TableRow key={station.id_mongo}>
                  <TableCell>
                    {station.logoUrl ? (
                      <img src={station.logoUrl} className="w-8 h-8 rounded object-cover bg-black/10" />
                    ) : <div className="w-8 h-8 bg-muted rounded" />}
                  </TableCell>
                  <TableCell className="font-medium">{station.name}</TableCell>
                  <TableCell className="max-w-[200px] truncate text-xs">{station.streamUrl}</TableCell>
                  <TableCell className="text-xs">{station.language}<br/><span className="text-muted-foreground">{station.genre}</span></TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" onClick={() => handleOpenSheet(station)}>
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="text-destructive" onClick={() => {
                        if (confirm('Are you sure you want to delete this station?')) {
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
            <SheetTitle>{editingStation ? "Edit Station" : "Add New Station"}</SheetTitle>
            <SheetDescription>Make changes to the station database record here. All fields are required except ID.</SheetDescription>
          </SheetHeader>
          <div className="grid gap-4 py-4">
            {["name", "streamUrl", "logoUrl", "language", "genre", "page", "id"].map((field) => (
              <div key={field} className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor={field} className="text-right capitalize">
                  {field === "page" ? "Slug (Page)" : field}{field !== "id" && " *"}
                </Label>
                <Input
                  id={field}
                  value={formData[field as keyof DBStation] || ""}
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
