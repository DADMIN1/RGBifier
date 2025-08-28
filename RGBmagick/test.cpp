#include <iostream>
#include <format>
#include <vector>
#include <filesystem>

#include <Magick++.h>
//#include <magick/MagickCore.h>


extern "C" { // libRGBmagick.so exports //
void PythonPlz(const wchar_t ezString[]) { // easy for python, that is. python strings are UTF8 (wchar_t)
	std::cout << "\r"; // something must be written to std::cout before ever using std::wcout; otherwise,
	// output will never appear on std::cout!! (affects everything; executable and shared-library/FFI.py)
	std::wcout << L"  [PythonPlz]: " << ezString << std::endl;
}

int EpicFunction(int argc, const char* argv[]) {
	for (int C{0}; C < argc; C++) {
		std::cout << "  [EpicFunction]: ";
		std::cout << C << ": " << argv[C] << '\n';
	}
	return 69;
}

const char* GetImageSize(const char imagepath[]) {
	static std::string _ImageSizeString{"[0x0]"};
	try { Magick::Image testimage(imagepath); testimage.verbose(true);
		_ImageSizeString = std::format("[{}x{}]", testimage.columns(), testimage.rows());
	} catch (Magick::ErrorBlob& error){ _ImageSizeString = std::format("[ERROR] {}", error.what());}
	return _ImageSizeString.c_str();
}

}// extern "C"


// Magick::readImages doesn't accept format-specifiers ("frame%03d.png"); image sequences must be loaded manually
std::vector<Magick::Image> LoadImageDirectory(std::string directory) {
	std::vector<Magick::Image> imageList{}; imageList.reserve(1000);
	// this iterates the files in REVERSE order
	for(std::filesystem::directory_entry const& file: 
		std::filesystem::directory_iterator{directory}) {
		imageList.push_back(Magick::Image(file.path()));
	}
	std::cout << std::format("loaded '{}' [{} images]", directory, imageList.size()) << '\n';
	return imageList;
}
// TODO: need to filter out the '.cache' files when loading MPC-frames
// if (file.path().extension() == ".mpc")

void ImageGrid(std::vector<Magick::Image>& imagelist, int stacklength, bool vert)
{
	std::vector<Magick::Image> stacks{}; stacks.reserve(25);
	// segfaults if framestacks aren't all the same length
	if ((imagelist.size() % stacklength) != 0) {
		std::cout << std::format(
			"[WARNING] imagelist[{}] is not divisible by stacksize: {}[+{}]",
			imagelist.size(), stacklength, (imagelist.size() % stacklength)
		) << '\n';
		for (auto rem{(imagelist.size() % stacklength)}; rem > 0; --rem)
			imagelist.pop_back(); // resize until evenly divisible
		std::cout << "new length: " << imagelist.size() << '\n';
	}
	
	for(auto iter {imagelist.rbegin()}; iter < imagelist.rend();) {
	/*	std::cout << "next stack: " << iter->fileName() << '\n'; */
		Magick::Image& stacked{stacks.emplace_back()};
		Magick::appendImages(&stacked, iter, iter+stacklength, vert); // vertical
		stacked.scale("25%"); // TODO: configurable. also encode in filename
		iter += stacklength;
	}
	
	Magick::Image framegrid{};
	Magick::appendImages(&framegrid, stacks.begin(), stacks.end(), !vert); // horizontal
	std::cout << std::format("grid: [{}x{}]", stacks.size(), stacklength);
	std::cout << std::format("({}x{})", framegrid.columns(), framegrid.rows()) << '\n';
	std::string filename = std::format("image_grid_{}_{}_[{}x{}].png",
		(vert?'v':'h'), imagelist.size(), stacks.size(), stacklength);
	framegrid.write("PNG:/tmp/RGB_TOPLEVEL/output/"+filename);
	return;
}


// stripped from library //
#ifndef IS_LIBRARY_BUILD
void PrintBuildInfo() {
	std::cout << "RGBmagick!!!";
	#ifdef MAGICKCORE_QUANTUM_DEPTH
	std::cout << " [QUANTUM_DEPTH: " << MAGICKCORE_QUANTUM_DEPTH << ']';
	#endif
	std::cout << '\n';
	
	#if MAGICKCORE_HDRI_ENABLE
	std::cout << "HDRI support enabled!!!\n";
	#endif
	
	#ifdef MAGICKCORE_MODULES_RELATIVE_PATH
	// I think this and a few other variables in "magick-config.h" should be defined...
	std::cout << "MAGICKCORE_MODULES_RELATIVE_PATH: " << MAGICKCORE_MODULES_RELATIVE_PATH << '\n';
	#endif
}

int main(int argc, const char* argv[])
{
	PrintBuildInfo();
	std::cout << "argc: " << argc << '\n';
	for (int C{0}; C < argc; C++) {
		std::cout << C << ": ";
		std::cout << argv[C] << '\n';
	}
	
	// ImageMagick will write temp/cache files to the current directory if TEMP_IM doesn't exist
	std::vector<std::filesystem::directory_entry> tempdirs {
		std::filesystem::directory_entry{"/tmp/RGB_TOPLEVEL/TEMP_IM/"},
		std::filesystem::directory_entry{"/tmp/RGB_TOPLEVEL/TEMP_GM/"},
		std::filesystem::directory_entry{"/tmp/RGB_TOPLEVEL/inputs/"},
		std::filesystem::directory_entry{"/tmp/RGB_TOPLEVEL/output/"},
	}; for (const std::filesystem::directory_entry& path: tempdirs) {
		if (!path.exists()) std::filesystem::create_directory(path);
	}
	
	std::cout << '\n';
	PythonPlz(L"Plz Print This WideString Plz C++");
	EpicFunction(argc, argv);
	std::cout << '\n';
	
	std::cout << "testimages/peach.png\n";
	Magick::Image testimage("testimages/peach.png");
	std::cout << testimage.magick() << '\n'; // PNG
	std::cout << GetImageSize("testimages/peach.png") << '\n';
	std::cout << '[' << testimage.columns() << 'x' << testimage.rows() << "]\n";
	std::cout << std::endl;
	
	std::vector<Magick::Image> imagelist = LoadImageDirectory("/tmp/RGB_TOPLEVEL/inputs/");
	// good divisors for length 100
	ImageGrid(imagelist,  4, true);
	ImageGrid(imagelist,  5, true);
	ImageGrid(imagelist, 10, true);
	ImageGrid(imagelist, 20, true);
	ImageGrid(imagelist, 25, true);
	
	return 0;
}

#endif //NOT_LIBRARY_BUILD
