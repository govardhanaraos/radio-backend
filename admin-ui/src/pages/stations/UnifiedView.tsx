import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Search } from "lucide-react";

interface Station {
  id: string;
  name: string;
  logoUrl: string;
  streamUrl: string;
  language: string;
  genre: string;
  page: string;
}

export default function UnifiedView() {
  const [page, setPage] = useState(1);
  const [limit] = useState(50);
  const [languageFilter, setLanguageFilter] = useState("");
  const [genreFilter, setGenreFilter] = useState("");

  const { data: stations, isLoading, error } = useQuery({
    queryKey: ["stations", page, limit, languageFilter, genreFilter],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
      });
      if (languageFilter) params.append("language", languageFilter);
      if (genreFilter) params.append("genre", genreFilter);

      const res = await apiClient.get<Station[]>(`/stations/?${params.toString()}`);
      return res.data;
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Unified Directory (Read-Only)</CardTitle>
        <CardDescription>
          Displaying combined paginated stations (Page {page}).
        </CardDescription>
        <p className="text-xs text-muted-foreground">
          Collection: <span className="font-mono">radio_stations</span> + <span className="font-mono">radio_garden_channels</span> | Key: <span className="font-mono">_id (returned as id)</span>
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center justify-between">
          <div className="flex flex-1 items-center space-x-2">
            <div className="relative flex-1 md:max-w-xs">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="search"
                placeholder="Filter by language..."
                className="pl-8"
                value={languageFilter}
                onChange={(e) => {
                  setLanguageFilter(e.target.value);
                  setPage(1);
                }}
              />
            </div>
            <div className="relative flex-1 md:max-w-xs">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="search"
                placeholder="Filter by genre..."
                className="pl-8"
                value={genreFilter}
                onChange={(e) => {
                  setGenreFilter(e.target.value);
                  setPage(1);
                }}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              disabled={!stations || stations.length < limit}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>

        <div className="rounded-md border mt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[80px]">Logo</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Language</TableHead>
                <TableHead>Genre</TableHead>
                <TableHead className="hidden md:table-cell">Stream URL</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-24 text-center">Loading stations...</TableCell>
                </TableRow>
              ) : error ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-24 text-center text-destructive">
                    Error loading stations. Ensure backend is running.
                  </TableCell>
                </TableRow>
              ) : stations?.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                    No stations found.
                  </TableCell>
                </TableRow>
              ) : (
                stations?.map((station) => (
                  <TableRow key={station.id || Math.random().toString()}>
                    <TableCell>
                      {station.logoUrl ? (
                        <img
                          src={station.logoUrl}
                          alt={station.name}
                          className="w-8 h-8 rounded mt-1 object-cover bg-muted"
                          loading="lazy"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdib3g9IjAgMCAyNCAyNCI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTAiIGZpbGw9IiNlMGUwZTAiLz48L3N2Zz4='; // fallback gray circle
                          }}
                        />
                      ) : (
                        <div className="w-8 h-8 rounded bg-muted" />
                      )}
                    </TableCell>
                    <TableCell className="font-medium">{station.name}</TableCell>
                    <TableCell>{station.language}</TableCell>
                    <TableCell>{station.genre}</TableCell>
                    <TableCell className="hidden md:table-cell max-w-[200px] truncate">
                      <a href={station.streamUrl} target="_blank" rel="noreferrer" className="text-primary underline hover:no-underline">
                        {station.streamUrl}
                      </a>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
