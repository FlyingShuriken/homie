"use client";

import { useState } from "react";
import {
  GoogleMap,
  InfoWindow,
  Marker,
  useJsApiLoader,
} from "@react-google-maps/api";

interface TransportStop {
  name: string;
  lat: number;
  lng: number;
}

interface ListingMapProps {
  lat: number;
  lng: number;
  title: string;
  transportStops?: TransportStop[];
}

const MAP_CONTAINER_STYLE = { width: "100%", height: "280px" };

const TRANSIT_ICON = {
  path: "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z",
  fillColor: "#2563eb",
  fillOpacity: 1,
  strokeColor: "#ffffff",
  strokeWeight: 1.5,
  scale: 1.2,
  anchor: { x: 12, y: 22 } as google.maps.Point,
};

export default function ListingMap({
  lat,
  lng,
  title,
  transportStops = [],
}: ListingMapProps) {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";
  const [activeStop, setActiveStop] = useState<TransportStop | null>(null);

  const { isLoaded } = useJsApiLoader({ googleMapsApiKey: apiKey });

  if (!apiKey || !isLoaded) return null;

  const center = { lat, lng };

  return (
    <div className="rounded-xl overflow-hidden border border-stone-200">
      <GoogleMap
        mapContainerStyle={MAP_CONTAINER_STYLE}
        center={center}
        zoom={15}
        options={{ disableDefaultUI: true, zoomControl: true }}
      >
        {/* Listing pin */}
        <Marker position={center} title={title} />

        {/* Transit stop pins */}
        {transportStops.map((stop) => (
          <Marker
            key={stop.name}
            position={{ lat: stop.lat, lng: stop.lng }}
            title={stop.name}
            icon={TRANSIT_ICON}
            onClick={() => setActiveStop(stop)}
          />
        ))}

        {activeStop && (
          <InfoWindow
            position={{ lat: activeStop.lat, lng: activeStop.lng }}
            onCloseClick={() => setActiveStop(null)}
          >
            <p className="text-xs font-medium text-stone-800">{activeStop.name}</p>
          </InfoWindow>
        )}
      </GoogleMap>

      {transportStops.length > 0 && (
        <div className="flex items-center gap-4 px-3 py-2 bg-stone-50 border-t border-stone-200 text-xs text-stone-500">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-[#ea4335]" />
            Listing
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-blue-600" />
            Transit stop
          </span>
        </div>
      )}
    </div>
  );
}
