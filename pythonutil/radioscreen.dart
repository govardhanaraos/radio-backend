import 'dart:async';
import 'package:audio_service/audio_service.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:grradio/ads/ad_helper.dart';
import 'package:grradio/ads/banner_ad_widget.dart';
import 'package:grradio/ads/insterstitialadmanager.dart';
import 'package:grradio/ads/rewardedads.dart';
import 'package:grradio/main.dart';
import 'package:grradio/radioplayerhandler.dart';
import 'package:grradio/radiostation.dart';
import 'package:grradio/responsebutton.dart';
import 'package:grradio/api_service.dart'; // Ensure this import exists

class RadioPlayerScreen extends StatefulWidget {
  final Function(bool) onRecordingStatusChanged;
  final dynamic onNavigateToMp3Tab;
  final dynamic onNavigateToRecordings;

  const RadioPlayerScreen({
    Key? key,
    required this.onNavigateToMp3Tab,
    required this.onNavigateToRecordings,
    required this.onRecordingStatusChanged,
  }) : super(key: key);
  @override
  State<RadioPlayerScreen> createState() => _RadioPlayerScreenState();
}

class _RadioPlayerScreenState extends State<RadioPlayerScreen>
    with TickerProviderStateMixin {
  late AudioHandler _audioHandler;
  late AnimationController _animationController;
  late Animation<double> _animation;
  MediaItem? _currentMediaItem;
  PlaybackState? _playbackState;
  StreamSubscription<MediaItem?>? _mediaItemSubscription;
  StreamSubscription<PlaybackState>? _playbackStateSubscription;
  String _searchQuery = '';
  
  List<RadioStation> allRadioStations = [];
  bool _isLoading = true;

  // Instance of the API service
  final RadioApiService _apiService = RadioApiService();

  @override
  void initState() {
    super.initState();
    _initializeAudioHandler();
    _loadStations();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    )..repeat(reverse: true);
    _animation = Tween<double>(begin: 0.9, end: 1.1).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );
  }

  void _initializeAudioHandler() async {
    _audioHandler = await AudioService.systemAudioHandler;
    _mediaItemSubscription = _audioHandler.mediaItem.listen((item) {
      if (mounted) {
        setState(() {
          _currentMediaItem = item;
        });
      }
    });

    _playbackStateSubscription = _audioHandler.playbackState.listen((state) {
      if (mounted) {
        setState(() {
          _playbackState = state;
        });
      }
    });
  }

  // --- REWRITTEN LOGIC TO FETCH STATIONS ---
  Future<void> _loadStations() async {
    setState(() {
      _isLoading = true;
    });

    try {
      // 1. Fetch data. The service ALREADY returns List<RadioStation>.
      // We do not need to use .map() here.
      final stations = await _apiService.fetchRadioStations();

      print('Loaded ${stations.length} stations from MongoDB.');

      if (mounted) {
        setState(() {
          // 2. Assign directly.
          allRadioStations = stations;
          _isLoading = false;
        });
      }
    } catch (e) {
      print('Failed to load radio stations: $e');
      if (mounted) {
        setState(() {
          allRadioStations = []; // Ensure list is empty on error
          _isLoading = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _mediaItemSubscription?.cancel();
    _playbackStateSubscription?.cancel();
    _animationController.dispose();
    super.dispose();
  }

  bool _isPlaying(RadioStation station) {
    return _currentMediaItem?.id == station.id &&
        _playbackState?.playing == true;
  }

  void _playStation(RadioStation station) {
    if (_isPlaying(station)) {
      _audioHandler.pause();
    } else {
      _audioHandler.customAction('playNew', {
        'id': station.id,
        'title': station.name,
        'artist': station.state ?? 'Radio Station',
        'streamUrl': station.streamUrl,
        'logoUrl': station.logoUrl,
      });
    }
  }

  List<RadioStation> get _filteredStations {
    if (_searchQuery.isEmpty) {
      return allRadioStations;
    }
    final query = _searchQuery.toLowerCase();
    
    return allRadioStations
        .where(
          (station) =>
              station.name.toLowerCase().contains(query) ||
              (station.state?.toLowerCase().contains(query) ?? false) ||
              (station.language?.toLowerCase().contains(query) ?? false)
        )
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('GR Radio'),
        actions: [
          IconButton(
            icon: const Icon(Icons.mic),
            onPressed: widget.onNavigateToRecordings,
          ),
          IconButton(
            icon: const Icon(Icons.headphones),
            onPressed: widget.onNavigateToMp3Tab,
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: TextField(
              decoration: const InputDecoration(
                labelText: 'Search by Name, State, or Language',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: (value) {
                setState(() {
                  _searchQuery = value;
                });
              },
            ),
          ),
          const BannerAdWidget(),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _buildStationList(),
          ),
        ],
      ),
    );
  }

  Widget _buildStationList() {
    return AnimatedBuilder(
      animation: _animationController,
      builder: (context, child) {
        if (_filteredStations.isEmpty && !_isLoading) {
             return const Center(child: Text("No stations found"));
        }
        return ListView.builder(
          itemCount: _filteredStations.length,
          itemBuilder: (context, index) {
            final station = _filteredStations[index];
            final isPlaying = _isPlaying(station);
            
            return ListTile(
              title: Text(
                station.name,
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: RButton.getMediumFontSize(),
                ),
              ),
              subtitle: Text(
                '${station.state ?? 'Unknown State'} | ${station.language ?? 'Unknown Language'}',
                style: TextStyle(fontSize: RButton.getSmallFontSize()),
              ),
              leading: station.logoUrl != null && station.logoUrl!.isNotEmpty
                  ? ScaleTransition(
                      scale: isPlaying ? _animation : const AlwaysStoppedAnimation(1.0),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: Image.network(
                          station.logoUrl!,
                          width: RButton.getListIconSize(),
                          height: RButton.getListIconSize(),
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) {
                            return Container(
                              width: RButton.getListIconSize(),
                              height: RButton.getListIconSize(),
                              color: Colors.grey[200],
                              child: Icon(
                                Icons.broken_image,
                                color: Colors.red[400],
                                size: RButton.getListIconSize(),
                              ),
                            );
                          },
                        ),
                      ),
                    )
                  : CircleAvatar(
                      child: Icon(Icons.radio, size: RButton.getListIconSize()),
                    ),
              trailing: isPlaying
                  ? Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.green,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        'PLAYING',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: RButton.getExSmallFontSize(),
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    )
                  : const SizedBox.shrink(),
              onTap: () {
                _playStation(station);
              },
            );
          },
        );
      },
    );
  }
}